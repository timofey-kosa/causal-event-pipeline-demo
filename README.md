# Standing Upstream

![CI](https://github.com/timofey-kosa/causal-event-pipeline-demo/actions/workflows/ci.yml/badge.svg)

A research programme on one recurring dislocation — Uniswap V3 on Base against the Binance perpetual, ETH/USDC — told as it unfolded: a trade idea, tested and narrowed in stages, each stage pointing one step further upstream toward whatever was actually moving the market.

```text
ETH/USDC · Uniswap V3 on Base ↔ Binance USD-M perpetual · research 2026-05-06 → 2026-09-16
All returns gross, in basis points · holdout 2025-09 onward sealed and unread
```

> **About this repository.** This page is the research report. The code in this repository is a separate, self-contained
> [causal event-pipeline demo](docs/pipeline-demo.md) that reproduces the methodology on **synthetic data**: event-time
> alignment of two asynchronous feeds, strict pre-/post-event separation, no-lookahead validation, embargoed temporal
> cross-validation with bootstrap intervals, and checksum-frozen runs. The raw data, run artefacts and research code behind
> the report are private; the `artifacts/…`, `db/…` and `EVD-…` references under each section name them.
> The original typeset report is in [`docs/standing-upstream.html`](docs/standing-upstream.html).

**Contents** — [00 How this started](#00--how-this-started-and-where-it-stands) ·
[01 Data, clocks and universes](#01--data-clocks-and-universes) ·
[R1 Is the spread just Binance, seen late?](#r1--is-the-spread-just-binance-seen-late) ·
[R2 Does the price keep going?](#r2--does-the-price-keep-going--and-can-anything-tell-which-way) ·
[R3 Best prices on top of the trade tape](#r3--best-prices-on-top-of-the-trade-tape) ·
[R4 After entry](#r4--after-entry) ·
[R5 Liquidations](#r5--liquidations-upstream-of-the-flow) ·
[R6 What is being recorded](#r6--what-is-being-recorded-and-for-which-open-question) ·
[X Open experiments](#x--open-experiments) ·
[A Defect register](#a--defect-register)

---

## 00 · How this started, and where it stands

The starting idea was simple: when a Uniswap pool and its matching Binance perpetual disagree by more than a few basis points, something has not caught up, and a real move is often already under way. Trade the gap.

The first real work was sizing both legs of that idea, and it retired one of them immediately. Ten seconds after a dislocation opens, the Uniswap leg has moved **+12.84 bp** and the Binance leg **+0.25 bp** — fifty to one. The dislocation is the pool catching up with Binance, not two markets converging on each other, and closing it on the DEX side is a latency race already won by someone else: Wu, Sui, Thiery and Pai ([arXiv:2507.13023](https://arxiv.org/abs/2507.13023)) measure $233.8 m captured across 7.2 m CEX–DEX arbitrages on Ethereum, with the top three searchers alone taking 73 → 90 % of that flow by 2025. That leg was set aside — not because it has no value, but because it is won by infrastructure speed, not by analysis.

What was left was the Binance leg: could the dislocation say anything about what Binance was about to do? Answering that meant understanding what actually produces a dislocation, and every layer of that understanding pushed the question further upstream. A dislocation turned out to be a symptom of Binance taker flow (R1); that flow turned out to be a symptom of continuation in the Binance price itself, which is real but directionless at every resolution measured (R2); the order book one level down carried the same shape — a little information about size, almost none about direction, and gone within milliseconds (R3); and once a position was open, no exit rule and no sequence model ever recovered direction from the price path alone (R4). The same result kept recurring in a different costume:

```text
spread  →  taker flow  →  Binance's price  →  the book  →  forced liquidations
  R1           R1               R2               R3                R5
```

**Amplitude is measurable at every rung; direction is not — until the chain runs out at the one place direction is not read off the market but created by it.** A forced liquidation is, by construction, a one-sided order with a known side. That is where this stands now (R5), and it is the first place the amplitude this programme kept finding has something to attach a direction to, if the price levels those forced orders come from can be located in advance.

That last piece — a map of where leveraged positions sit, priced against the current market to say when and how hard a level gets hit — already exists as a product category: liquidation heatmaps, built on assumed leverage brackets, are a standard feature of crypto trading terminals. The version built and tested here (R5) uses that same construction and gets the same non-result: fixed leverage bands place liquidations no better than a plain volume profile. The question this programme is now working (X4) is whether replacing assumed leverage with leverage estimated from data, and a density with a probability of reaching a level, turns a descriptive map into a timing signal — without competing on latency at all.

- **Cards.** Every experiment below is a card: question, setup, universe, features, result.
- **Order.** Experiments on one question run from fewer inputs to more; the fuller model has to confirm the lighter one.
- **Evidence.** A result counts when its 95 % day-clustered bootstrap interval excludes zero (0.5 for an AUC). Otherwise it is given as a number with its interval, not as a claim.
- **Inputs.** No model receives a direction-carrying ratio (a signed quantity divided by its own magnitude); numerator and denominator go in separately — the defect register shows what that rule cost to learn the hard way.

## 01 · Data, clocks and universes

| tape | what it holds | resolution | span |
|---|---|---|---|
| Uniswap V3 swaps, Base | pool price per swap | block time; ~2 s blocks built from 200 ms flashblocks | 2023-09 → 2026-05 |
| Binance aggTrades, signed | taker orders with their side | milliseconds, per event | 2024-01 → 2026-05 |
| `spread_series` | `1e4·(p_bin − p_uni)/p_bin`, event-time join of both | every event of either venue | 29 months |
| Binance bookTicker archive | best bid, best ask, quantities at both | per event, 3 ms median gap | 2024-01-05 → 2024-03-30 |
| CoinAPI L2 and BBO | order book by level; its top | 100 ms frames, receipt stamps | 191 days, 2024-11-26 → 2025-08-29 |
| CoinAPI liquidations | minute bars; trade time `T` and price of each order; no side | minute bars, `T` in ms | the same 191 days |
| Binance `metrics` archive | open interest, positioning ratios | 5 minutes, no missing days | 2024-01-04 → 2025-08-29 |

**One clock for every experiment.** Binance stamps trades in milliseconds and many share one; prints are ordered by time, then by the exchange's trade id, so "the last print" is the exchange's last.

| event | usable from |
|---|---|
| a Binance print | +15 ms |
| a Uniswap price, inside the spread | block time + 160 ms |
| a spread crossing made by a Binance print | +15 ms |
| a spread crossing made by a new Uniswap price | block time + 160 ms |
| a market order's fill | +40 ms after the decision |

<sub>Delays round up to the data step. The CoinAPI book arrives in 100 ms frames, so on that tape nothing finer than 100 ms is measured.</sub>

**Universes, defined once.** A fold is a calendar window: fold 1 is 2024-11-26 → 2025-02-13, fold 2 is 2025-02-14 → 2025-04-08. An episode opens when the spread rises above 6 bp and closes when it falls below 3 bp.

| id | what it is | n | span | used in |
|---|---|--:|---|---|
| **UA** | anchors of three independent kinds, both directions: A1 spread crossings; A2 bursts of signed Binance volume; A3 departures of the Binance price from its own 60 s mean by more than its own volatility — no spread term | fold 1: 141,688 / 15,052 / 57,455<br>fold 2: 122,007 / 39,579 / 73,200 | folds 1–2, every calendar day (80 + 54) | R2 |
| **UB** | 8 bp jumps of the Binance mid, and episode opens, on the native bookTicker tape | 6,401 jumps<br>5,859 opens | 2024-01-05 → 2024-04-01, 87 days | R3 |
| **U2** | episodes with an out-of-fold pre-entry score, split into five equal chronological folds of 51,176 (fold 0 trains only) | 255,881 | 2024-08 → 2025-08 | R1, R4 |
| **U3** | U2 episodes above the entry gate — the 0.90 quantile of the score over earlier folds | 28,467 | folds 1–4 | R4 |
| **U5** | fold-1 entries of U3 with a reconstructed CoinAPI book | 9,817 | fold 1, 61 days | R3, R4 |
| **UL** | liquidations at the trade time `T` of each minute's first order, with matched quiet instants | 19,709 / 150,154 | 191 CoinAPI days | R5 |
| **UH** | fold-1 A1 breaches, split by liquidation background | 5,658 | 63 days | R5 |
| **UM** | open interest and trades for building liquidation maps; liquidations to test them | 604 days | 2024-01-04 → 2025-08-29 | R5 |

## R1 · Is the spread just Binance, seen late?

The cheapest deflation of the whole programme: the spread is Binance seen again a step later, and every study built on it was a Binance study in disguise. Three measurements take that apart — what the flow does around a breach, which venue actually moves, and what a ranker of episodes really reads.

### R1·1 — Taker flow around a breach

- **Question.** What does Binance taker flow do in the seconds before and after the spread breaks out?
- **Setup.** Taker imbalance in half-second bins from −105 s to +30 s around each episode open, against hour-matched random instants.
- **Universe.** Fold 1, 79 days: 5,574 episode opens, 5,574 controls. Background split on UH.
- **Features.** Signed and total taker volume, trade rate.
- **Result.** Imbalance stays inside [−0.070, +0.006] until 5 s before the breach, reaches +0.605 at −2.5 s and +0.657 in the last half-second, and is back to +0.027 by +1.5 s; trade rate 10.8/s → 34.2/s → 13.7/s. **A breach is a three-second one-sided flow event, not a build-up.**
  On a quiet background the flow ramps early: +0.165 [+0.012, +0.365] at −5.5 s, +0.797 [+0.240, +0.919] at −2.5 s. With liquidations already known before the breach there is no ramp until −1.5 s (+0.191 [+0.084, +0.421]), and the breach itself is weaker: 48.7 ETH/s against 88.4.
  The side is carried by signed trade counts rather than signed volume (0.664 against 0.635 AUC over 30 s at a 2 s lead, on 11,127 two-sided crossings); volume alone is at chance, 0.510.

![Taker imbalance around a breach](docs/assets/figures/r1-taker-imbalance-around-breach.svg)

<sub>R1·1. Binance taker imbalance around a spread breach, fold 1, shaded 95 % day-clustered interval. Flat until five seconds before, one-sided for three, gone within two after. Source: `artifacts/breach_binance_flow_v1/results.json`.</sub>

### R1·2 — Which leg closes the spread

- **Question.** When the spread closes, which venue moves?
- **Setup.** Price change of each leg from the episode open to +10 s.
- **Universe.** Fold 1, 5,574 episode opens.
- **Result.** Uniswap **+12.84 bp**, Binance **+0.25 bp**. **The spread is the pool catching up with Binance**, not a two-sided mispricing. The Binance leg earns +0.32 bp by 2 s and −2.01 bp by 60 s.

### R1·3 — What a ranker of episodes actually reads

- **Question.** Given that the spread has selected an episode, does its shape add anything to ranking the move that follows?
- **Setup.** One model, four nested feature arms; target: maximum excursion within 30 s ≥ 10 bp; out-of-fold AUC.
- **Universe.** U2.
- **Features.** Calendar → + Binance tape → + Uniswap activity → + spread shape.
- **Result.**

  | arm | features | AUC | top decile, mean 30 s excursion |
  |---|--:|--:|--:|
  | calendar only | 8 | 0.6939 | 18.43 bp |
  | + Binance tape | 25 | 0.7337 | 22.46 bp |
  | + Uniswap activity | 39 | 0.7344 | 22.23 bp |
  | + spread shape | 52 | 0.7353 | 22.22 bp |

  Pool mean 9.01 bp. The spread's shape adds +0.0009 [+0.0002, +0.0017] AUC. **The ranking is the clock and the Binance tape.**

> **From the other side of the trade.** Wu, Sui, Thiery and Pai ([arXiv:2507.13023](https://arxiv.org/abs/2507.13023)) observe CEX–DEX arbitrage on Ethereum from the searchers who capture it: $233.8 m over 7.2 m arbitrages, nearly all under 20 bp gross, with the top three searchers growing from 73 % to about 90 % of the flow by 2025. The pool's late leg is a crowded, well-served trade.

**Verdict.** The spread is not Binance seen late — it is the pool arriving late. The move that closes it happens on Uniswap. Binance flow warns about three seconds ahead, and earlier only on a quiet background. What ranks opportunities is the calendar and the Binance tape.

<sub>**Evidence.** `EVD-BREACH-FLOW-NULL`; `artifacts/breach_binance_flow_v1/results.json` and `audit_2026-09-14/p14_result.json` (background split from `T`); `EVD-VENUE-ABLATION`, `artifacts/preentry_fat_gross_v1/c1c2/venue_ablation.json`.</sub>

## R2 · Does the price keep going — and can anything tell which way?

R1 measures the side of a spread crossing, which is the spread's own threshold. The trader's question is different: once a dislocation is visible, does the Binance price keep moving, and does anything say in which direction? R2 asks it on three anchor kinds, one of which is built from the Binance tape alone, so that the spread has to earn its place on events it did not define.

### R2·1 — Continuation against a random instant

- **Question.** After an anchor, does the Binance price keep moving in the anchor's direction, and for how long?
- **Setup.** Realised signed move from the fill to each point of a 12-point grid (0.5–60 s), against a 1:1 hour- and sign-matched random instant. The horizon is the last grid point before the first step whose interval covers zero.
- **Universe.** UA, fold 1.
- **Features.** None.
- **Result.** On A1 every step clears zero through 3 s; the next step, 3 → 5 s, is +0.022 [−0.005, +0.050]. **Horizon: 3 s.** Move at 3 s over the random instant: A1 long +0.337, A1 short +0.261, A2 +0.342, A3 +0.235 bp. A1 reaches +0.299 by 3 s and +0.392 by 60 s — **nine tenths of the move arrives in three seconds.**

![Continuation arrives in three seconds](docs/assets/figures/r2-continuation-horizon.svg)

<sub>R2·1. Realised move in the anchor's direction, fold 1. At 3 s: A1 +0.299, A2 +0.342, A3 +0.235 bp; beyond that the paths wander around their 3 s level while the matched instant stays at zero. Source: `artifacts/continuation_v1/horizon.json`.</sub>

### R2·2 — The direction of continuation: flow against spread

- **Question.** Can Binance flow or the spread say in advance which way continuation goes?
- **Setup.** Label: +4 bp before −4 bp within 3 s. LightGBM, nested in both directions around a common block. Fold 1 out-of-fold over five day blocks; fold 2 scored once by one fit on fold 1.
- **Universe.** UA, folds 1 and 2.
- **Features.** Common: Binance's own returns and realised volatility, regime, calendar. Flow: signed volume and volume, signed count and count, large-trade signed volume and volume, trailing windows. Spread: demeaned level, trailing velocities, RMS, breach geometry.
- **Result.**

  | anchors | fold | labelled | AUC flow | AUC spread | AUC both |
  |---|---|--:|--:|--:|--:|
  | A1 crossings | 1 | 36,071 | 0.4955 | 0.5053 | 0.5009 |
  | A1 crossings | 2 | 36,673 | 0.4998 | 0.4977 | 0.4992 |
  | A2 flow bursts | 1 | 3,835 | 0.4863 | 0.4992 | 0.4901 |
  | A2 flow bursts | 2 | 11,657 | 0.4979 | 0.5034 | 0.4989 |
  | A3 Binance only | 1 | 14,504 | 0.5084 | 0.5056 | 0.5080 |
  | A3 Binance only | 2 | 22,910 | 0.5026 | 0.4985 | 0.4981 |

  54–56 % of labelled anchors reach +4 first, yet every AUC is at chance; across all 60 cells of the grid, 0.47–0.54. At 30 s, with far more anchors resolved, the same: 0.4843–0.5075. The question of which variable adds to which never arises.

**Verdict.** Continuation is real and short — about 0.3 bp over a random instant, nine tenths of it within three seconds. Neither Binance flow nor the spread knows its direction: not on crossings, not on flow bursts, and not on departures built from the Binance tape alone.

**Next.** X1 — the full order book on the same anchors.

<sub>**Evidence.** `artifacts/continuation_v1/`: `PREREG.md`, `horizon.json`, `results_fold1.json`, `results_fold2.json`; `EVD-CONTINUATION-NULL`, `EVD-HORIZON-SELECTED`.</sub>

## R3 · Best prices on top of the trade tape

Upstream of the print is the quote. On 87 days of Binance's native bookTicker — best bid, best ask and the quantities at them, per event — R3 asks whether best prices add to the trade tape in predicting **(a)** whether a jump starts and **(b)** which way it goes.

**The jump origin.** A jump is an 8 bp move of the mid within a second. Its origin is the extremum of the mid in the second before the first 8 bp crossing. The origin is chosen in hindsight: it can only be identified at the crossing, a median 900 ms later. Leads count back from the origin, and every input is cut at origin − (lead + 15 ms).

### R3·1 — Is a jump coming?

- **Question.** Do best prices add to the trade tape in predicting that a jump is about to start?
- **Setup.** Jumps against controls matched on trade count; nested models at a 50 ms lead.
- **Universe.** UB: 3,888 jumps with a matched control.
- **Features.** Trade tape → + best bid and ask → + quantities at best prices, bid and ask delivered separately.
- **Result.** AUC 0.595 → 0.669 → 0.680: best prices add +0.085 [+0.061, +0.113], quantities +0.011 [+0.003, +0.018]. The mid's realised volatility over the last 5 s alone scores 0.648. **What best prices add is mostly the volatility regime a jump is born in.**

**Direction, briefly.** A companion test asks which way a jump goes, using the same nested features and a placebo built by the jump's own rule but without its 8 bp threshold. Best prices add +0.046 AUC to the jump's side at a 50 ms lead, falling to +0.015 by 100 ms and negligible beyond — carried almost entirely by the quote's own price, not its queue. The identical features add more and hold longer on the placebo, which says part of the increment on real jumps is an artefact of what makes something a "jump" at all rather than a directional signal. Both anchors are chosen in hindsight, so neither describes what could have been called in real time. Same conclusion as R2, in a different costume: the book does not resolve direction any earlier than the trade tape does.

### R3·2 — Enter before the breach, or after it?

- **Question.** With the breach known in advance, does a bid resting ahead of it beat a market order after it?
- **Setup.** A ceiling: the breach time is given. The taker buys the ask once the breach is visible (15 ms if a Binance print made it, 160 ms if a Uniswap price did — 8.9 % of opens) plus 40 ms, rounded up to the grid: 100 or 200 ms. The passive bid rests at the best bid from its lead until that moment; unfilled counts as zero. Exit at the best bid 3 s later.
- **Universe.** U5: 9,817 upward breaches, 61 days, CoinAPI 50 ms grid.
- **Features.** None.
- **Result.**

  | entry | filled | gross per attempt at 3 s |
  |---|--:|--:|
  | taker after the breach | — | +0.06 [−0.33, +0.57] |
  | bid 20 s ahead | 91 % | +3.87 [+3.10, +4.71] |
  | **bid 10 s ahead** | **87 %** | **+3.92 [+3.45, +4.26]** |
  | bid 5 s ahead | 82 % | +3.83 [+3.47, +4.45] |
  | bid 2 s ahead | 68 % | +2.95 [+2.69, +3.29] |
  | bid 1 s ahead | 48 % | +1.58 [+1.34, +1.89] |
  | bid 500 ms ahead | 29 % | +0.66 [+0.46, +0.93] |
  | bid 50 ms ahead | 12 % | −0.14 [−0.19, −0.06] |

  **The breach is where the move ends, not where it starts.** About 7 bp arrive in the two seconds around it; after that the mid is flat to 30 s.

![The breach is where the move ends](docs/assets/figures/r3-breach-mid-path.svg)

<sub>R3·2. The mid rises +1.09 bp from −10 s to −1 s, +3.58 in the last second and +2.05 in the next, then holds near +2.10 to 30 s. U5, 9,817 breaches. Source: `artifacts/preentry_maker_ceiling_v1/audit_2026-09-14/maker_path.json`.</sub>

**Verdict.** Best prices add to the trade tape, but not at a moment a decision can use. What they add to imminence is mostly the volatility regime; the side sits in the quote's own price and fades before the origin is even identifiable; the breach closes the move — a taker entering after it earns +0.06 bp at 3 s, a bid resting 10 s ahead +3.92.

**What flips it.** X1 and X2 — the full order book, at CoinAPI's 100 ms frames.

<sub>**Evidence.** `artifacts/lob_precursor_v1/c1c2/results_c2.json` and `audit_2026-09-14/` (placebo); `artifacts/preentry_maker_ceiling_v1/audit_2026-09-14/maker_path.json`; `EVD-LOB-PRECURSOR`.</sub>

## R4 · After entry

Most of the programme's effort went below the last rung: a position exists, and the question is when to leave it. Two results carry this section. Two more things turned out, on inspection, to be about the programme's own instruments rather than about the market — a pre-entry gate that had drifted off the score it was cutting, and a book measured only through ratios that understated what it knew — and are in the defect register with the rest of that kind of finding.

### R4·1 — Can an exit rule beat holding?

- **Question.** With a position open, can a rule that decides within 30 s exit better than holding to 30 s?
- **Setup.** Entry 40 ms after the open, at the last print; 50 ms decision grid, 600 ticks; baseline π0 = hold to 30 s. Statistic: gross difference against π0, day bootstrap.
- **Universe.** U3 for setups 1–5 (folds 2–4 out of fold); U5 for setup 6.
- **Features.** Twenty state features: current return; share of the 30 s elapsed; Binance return over 200 ms, 1 s, 5 s; the spread and its 1 s change; signed volume 1 s and 5 s, volume 1 s, trade count 1 s and 5 s, signed-volume share 1 s; Uniswap swaps since entry, a swap flag, time since the first swap; running maximum and minimum, drawdown, run-up. Setups 3–5 add the gate score; setup 5 adds nine spread-mechanics columns; setup 6 uses a 546-column bank.
- **Result.**

  | # | setup | model | against π0, bp |
  |--:|---|---|---|
  | 1 | optimal stopping π3 | random forest | −0.13 [−0.68, +0.37] |
  | 2 | take-profit ladder, 5–25 bp | none | −0.80 … −0.96, every interval below zero |
  | 3 | first touch of +5 or −10 bp | random forest | AUC 0.61 on all ticks, 0.52 on the ticks the policy acts on; −0.36 [−1.05, +0.26]. Changing the barriers relabels ≤ 4.7 % of episodes |
  | 4 | advantage of waiting | random forest | Spearman −0.001 on 10.45 m ticks; P(advantage < 0) ≈ 0.5 in every decile |
  | 5 | Bellman iteration | LightGBM | in sample +4.23; out of fold −0.22 [−0.99, +0.50] |
  | 6 | class routing | TCN | +22.3 / +21.2 on falling classes, −18.1 / −17.6 on rising; net +1.03, interval through zero |

  A perfect exit adds C = 9.254 bp over holding; a blind exit costs F = 9.483. A rule that catches every exit-worthy path beats holding only above 51 % precision. The best trained family reached 39 %.

### R4·2 — When do paths become distinguishable?

- **Question.** How early after entry can an episode's class be told apart? Classes sort each episode by its price path after entry, at 5 and 10 bp.
- **Universe.** U5 and fold-1/fold-2 cohorts, per row.
- **Result.**

  | study | universe | model | result |
  |---|---|---|---|
  | class mean paths | fold 1 | none | at +2 s all five within 0.67 bp (1.92 … 2.59); apart only after 10 s |
  | recognition against the class oracle | fold 1 | — | at 8 s captures +0.0398 bp of +11.15 [9.97, 11.94] |
  | four feature banks | fold 1, 7,853 episodes | TCN | exit-or-hold AUC at 8 s: 0.516–0.521 |
  | sequential baseline | fold 1 | LightGBM | AUC 0.576 at 6 s — it reads the spread regime, not the sequence |
  | sequence against trees | fold 2, 9,244 pairs | TCN, LightGBM | 0.5720 against 0.5803; path-only trees 0.5766 |
  | network tuning | fold 1 | TCN, 192 fits | AUC range across the grid 0.0064 |
  | feature capacity | fold 1, in sample | exit rule, 629 features | 2.08 of 9.12 bp of the class oracle, 21 %, measured on the training data |

  **Classes become distinguishable after the tradeable move is over.**

**Verdict.** No exit rule beat holding to 30 s: every interval contains zero or lies below it. Paths become distinguishable only after the tradeable move is over. Elsewhere in this section, an apparent collapse in the entry cohort and an apparent silence from the order book both turned out to be measurement artefacts, not market facts — see the defect register.

**What flips it.** X1 and X2.

<sub>**Evidence.** `EVD-C24`, `EVD-C14`, `EVD-C17`, `EVD-C20`, `EVD-C21`; `LGR-ARC-260710-BELLMAN-V2`, `LGR-ARC-260720-MORPH-T015`, `db/source/30-ledger/CHRONOLOGY/260719-lgbm-baseline.md`; `artifacts/continuation_v1/gate_diagnostic.md`; `artifacts/postentry_optstop_v1/audit_2026-09-14/`.</sub>

## R5 · Liquidations: upstream of the flow

Upstream of taker flow sit positions. A liquidation is a forced market order, and forced orders gather where leveraged positions break. If that structure is visible, it could say where and when the next move comes — and unlike everything above, it comes with a side attached by construction. Four cards follow the chain from the event back to the positions behind it.

### R5·1 — Does the price continue after a liquidation?

- **Question.** Does the price continue further after a liquidation than after an ordinary move of the same size at the same volatility?
- **Setup.** Entry at `T` + 1 s — Binance publishes a forced order up to about a second after the trade. Impulse = price change from 1 s before to 1 s after entry; continuation = move in the impulse's direction from entry. Controls matched on impulse size (6 bins) × previous-minute volatility (8 bins) × variance-rate tercile; weights by event composition; 1,000 day-bootstrap replicates.
- **Universe.** UL. Event size is the notional of the minute's first order, known at entry; top decile ≥ $13,669 (1,971 events).
- **Result.**

  | horizon | all events | top decile |
  |---|--:|--:|
  | 2 s | +0.07 [+0.02, +0.13] | −0.02 [−0.15, +0.12] |
  | **3 s** | **+0.09 [+0.01, +0.18]** | **+0.06 [−0.14, +0.26]** |
  | 10 s | +0.09 [−0.11, +0.34] | −0.17 [−0.60, +0.30] |
  | 60 s | +0.40 [+0.08, +0.76] | −0.49 [−1.36, +0.42] |
  | 300 s | +1.18 [+0.43, +1.96] | +1.07 [−0.44, +2.80] |

  Continuation is real across all liquidations — weak, but clear of zero out to 300 s — and not confirmed on the largest ones alone. Either way, **the move comes before the forced order.** In the 5–2 s before the trade the variance rate is 15.1 bp²/s against 0.82 for controls; over the preceding 10 s the price travels 9.16 bp against 1.90.

### R5·2 — Open interest and flow before a breach

- **Question.** Does a breach on a background of known liquidations run more often on closing risk than a breach on a quiet background?
- **Setup.** Background = liquidations with trade time between the end of the last closed 5-minute open-interest interval and the breach, known by then (`T` + 1 s ≤ breach), cut at the median non-zero notional. Measure: share of breaches with falling open interest, and with net selling flow, over that last closed interval; 2,000 day-bootstrap replicates. Second step: match on the direction and size of the Binance move over the same interval.
- **Universe.** UH.
- **Result.** Falling open interest: 61.5 % against 54.0 %, +7.4 pp [−2.9, +14.3], not separated. Net selling flow: 70.6 % against 54.8 %, +15.8 pp [+10.8, +21.6] — after matching on the price move, +3.8 pp [−0.9, +9.9]. Before liquidation-background breaches the price had fallen a median −32 bp against −4 bp. **The price fell and the tape sold: nothing beyond the move itself.**

### R5·3 — A map of liquidation levels

- **Question.** Does a map of where liquidations cluster say when the next breach comes, and where forced orders land?
- **Setup.**
  - *Timing:* notional-weighted density of executed liquidation prices over the previous 1, 3 or 7 days, 5 bp bins, per side; a cluster is a bin above the day's 90th percentile. Input: distance from the price to the nearest cluster on each side, every 10 s; target: time to the next breach in that direction; control: another day's map re-anchored to today's price; decided on fold 2.
  - *Resolution:* levels built from open-interest growth — each 5-minute interval with rising interest places entries at its VWAP, at leverage 10 / 25 / 50 / 100× with equal weights.
  - *Placement:* share of real liquidation notional landing in the map's top 10 % of bins, against a three-day volume profile with equal coverage.
- **Universe.** UM and UL; fold 2 (47 days) for timing, 191 days for placement.
- **Result.**
  - *Timing:* all 12 intervals against the control contain zero. "Near a cluster the breach takes longer" (Spearman to −0.24) is reproduced by a foreign day's map (to −0.18).
  - *Resolution:* the band of levels from one entry spans a median 974 bp for longs and 874 bp for shorts, against 62.5 bp between clusters — 14–16 times wider; 98 % of the width comes from unknown leverage.
  - *Placement:* +1.5 pp [−1.1, +4.0] over the volume profile.

### R5·4 — Erasing levels the price has already crossed

- **Question.** If levels the price has traversed are erased — those positions are already gone — does the map place liquidations better?
- **Setup.** A map built at 00:00 UTC from open-interest bricks of the previous N = 1 / 3 / 7 days. Erasure: longs above the lowest price since the brick, shorts below the highest. Decay exp(−λ·age), with λ the voluntary exit rate on fold 1 (0 / 0.0055 / 0.051 per hour). Leverage weights: equal, or tilted by the sign of accounts-versus-money positioning, or the reverse. 90 cells. Zone A is inside the three-day traded range; zone B runs beyond it to the deepest reachable level. Controls: uniform marking and a foreign period's map. Fold 2 decides; 187 days as a second reading.
- **Universe.** UM, UL.
- **Result.** Effect of erasure — zone B: −0.40 pp [−1.45, +0.43] on fold 2, −1.32 [−2.08, −0.70] on 187 days; zone A: −3.78 [−7.45, −0.21] and −2.36 [−4.27, −0.37]. Decay helps (λ = 0.0055 against none: +2.13 [+0.31, +4.14]); the positioning tilt does not (−1.82 [−10.9, +6.7]; its reverse +3.21 [−3.2, +10.8]). The mechanism shows why: 99.8 % of erasure falls inside the traded range, and new entries refill the erased mass — 39–48 % within a day, 61–81 % within a week. **What works is the freshness of entries, not the structure of leverage.**

**Verdict.** Continuation after a liquidation is real but weak and slow — the amplitude exists, it just does not arrive fast enough to act on after the largest events alone. What precedes a liquidation-background breach — falling interest, selling flow — restates the price move rather than adding to it. The level map built here fixed leverage at 10–100× with equal weights and was rebuilt once a day: it does not time a breach, it places liquidations no better than a volume profile, and erasing crossed levels does not improve it.

**Next.** Cheng, Deng, Wang and Yu (2021) estimate from BitMEX daily data that liquidated positions carry leverage of at least about 60× on average — the top of the range weighted equally here. The open plan replaces the density of levels with the probability of reaching one:

| | level map — run | reach probability — open (X4) |
|---|---|---|
| object | density of liquidation levels | probability of reaching a level |
| output | where | when, and with what probability |
| leverage | fixed, 10–100× equal weights | estimated from data, weighted to high leverage |
| boundary | static | drifts with funding |
| positions leaving | one decay constant | a rate that depends on market state |
| trigger | trade price | mark price |
| test | liquidation notional in marked bins | calibration and resolution |

<sub>**Evidence.** `artifacts/liquidation_reversion_v1/audit_2026-09-14/` (`p12`, `p22`–`p24`, `x3_*`); `artifacts/breach_binance_flow_v1/audit_2026-09-14/` (`p15`–`p17`); `DEF-F035`, `DEF-F036`; Cheng et al., [arXiv:2102.04591](https://arxiv.org/abs/2102.04591).</sub>

## R6 · What is being recorded, and for which open question

Every stream in the operator's recorder answers a question this programme could not test on the data it had. The recorder has run since 2026-08-03.

| open question | data | state |
|---|---|---|
| The book and forced liquidations below 100 ms, where the current vendor tape cannot resolve order | futures `@bookTicker`, `@depth@0ms` (WS 10, 11) | recorded |
| Liquidation cascades with side and event time | `!forceOrder@arr` — at most one order per symbol per second | planned |
| Is the trigger armed: mark price against contract price before a liquidation | `@markPrice@1s` (WS 13) together with `!forceOrder@arr` | mark recorded; high priority |
| Did a move open new risk or close old risk | `metrics` archive, 5 min, from 2024-01-04; finer snapshots via REST 47 | on disk |
| Positioning: many small accounts or few large ones | `metrics` archive; REST 49–52 | on disk |
| Funding | REST 53, full history | available |
| Spot–perp basis: derivative-led against index-led moves | spot trades archive from 2018-12-15; spot quote and book (WS 22, 23); index constituents (REST 54, current only) | recorded |
| Uniswap-only shape features | the swap tape | on disk, never tested |

**Verdict.** Every stream is tied to a question above or to confirming a book result. Four things cannot be recovered later: liquidations with their side; per-event quotes and book between 2024-03-30 and 2026-08-03; mark price finer than a minute; open-interest snapshots finer than five minutes. Each channel keeps a record of its own gaps, because a silent channel looks exactly like a quiet market.

<sub>**Evidence.** `audits/binance_grid_audit/`; `audits/binance_grid_audit/metrics_check_2026-09-14/`; `LGR-STALENESS-TAPES`.</sub>

## X · Open experiments

The book branch runs from fewer inputs to more: R2 (no book) → R3 (best prices) → X1 (full book) → X2. Its book features take four views of each price band at 1, 2, 4 and 8 bp: how much rests there, how it is distributed, how it changes and why, and the pressure against it. Sixty-three CoinAPI days are a single market regime, so a book signal found there is confirmed on a second period of the operator's own recorder, under a rule written before X1's first number.

### X1 — The full book and continuation

- **Question.** Does the full order book add to R2's prediction of continuation?
- **Setup.** R2 unchanged — anchors A1–A3, label +X before −Y, day blocks — plus book features at each anchor's decision instant. Arms: common + flow + spread against the same with the book, and common + book alone; a control on the same days without the book. Tuned on fold 1, tested on fold 2.
- **Universe.** UA on CoinAPI days: fold 1, 63 days; fold 2, 47 days.
- **Features.** R2's bank + nine book features per band.

### X2 — The full book and the next breach

- **Question.** Does the full book predict how soon the next upward and the next downward breach come?
- **Setup.** Two targets, one per direction; resistance is the asks for a breach up and the bids for a breach down.
- **Universe.** Fold 1, a continuous 10 s grid, 63 days.
- **Features.** The same nine book features per band.

<sub>X1 and X2 ask whether the full book adds anything to continuation or to breach timing — both currently null on the trade tape and on best prices alone. X4, at the end of the liquidations section, asks the question this programme is actually organised around: whether a probability of reaching a level, with leverage estimated from data rather than assumed, is where the direction missing since R2 finally shows up.</sub>

## A · Defect register

A good part of this programme's time was self-auditing rather than research. Every entry below was caught by checking a result against an independent reconstruction of the same number — an acceptance gate on a tape rebuild, an out-of-fold replay of an entry threshold, a bit-exact model refit — not by inspection. Three shapes recur often enough to name, and they group the register below: features encoded as ratios that quietly threw away the size of what they measured; clocks and selection rules that let a model see, or be scored on, information it would not have had live; and vendor tapes that resell a slower product than they advertise. None of the entries below changed a headline verdict in this report — each is either repaired, bounded, or shown not to move the conclusion it touches — but each is a specific, checkable claim about where this programme's own instruments could have lied to it, which is the standard the rest of its numbers are held to.

### Feature saturation

| defect | what it does | results on it | treatment |
|---|---|---|---|
| **Ratios in models** | a signed quantity divided by its own magnitude saturates at ±1 on short windows and discards size — the largest single source of understated results in this programme | every model on the original 51-column U2 feature set; the 546-column book bank in R4's setup 6 | de-ratioing Binance flow recovered +0.0014 AUC (R1); de-ratioing the order book's queue recovered +0.011 AUC on imminence and flipped its verdict from "no precursor" to a small real one (R3). Not recomputed everywhere the pattern appears |
| **Degenerate inputs** | a forest's score-based feature is constant within a fold; 156 of 546 bank columns are ≥ 50 % zeros, with missing values set to zero and no flag to say so | R4·1 | a bound on setups 1 and 6, not a repair |

### Measurement and selection

| defect | what it does | results on it | treatment |
|---|---|---|---|
| **Tie order** `DEF-F034` | the signed tape was written ordered by time only; 46.7 % of 354 m rows contradicted the exchange's trade id, so "last print" inside a millisecond was arbitrary | R1·3, R4 | repaired 2026-09-08; R1 re-run bit-identical; R2, R3, R5 built after the repair; R1·3 and R4 predate it and were not recomputed |
| **Gate drift** | the entry threshold was an absolute bar set from expanding history while the score it cut drifted down; supply held (17,988 → 19,207 episodes a month) and every fold's top-decile lift stayed clear of zero (+15.4 to +10.6 bp), but by 2025-08 the bar passed only 96 of 22,844 episodes | the fold-3/fold-4 entry counts (3,983, 1,403) read as "the market closed" | diagnosed 2026-09; a re-gated replay was not run — the shrinking cohort is evidence about the threshold, not the opportunity |
| **Clock of A1 and U2** | every A1 crossing and every U2 entry becomes usable 160 ms after the crossing, including crossings a Binance print made (usable at 15 ms) | R2 (A1), R4 | not recomputed: A2 and A3 run on the rule and give the same result; the deviation only delays entry. U2 rebuilt on this clock moves the target −0.211 bp on 64.3 % of episodes |
| **Decision clock after entry** | R4's exit features see Binance trades without the 15 ms and the spread and swaps without the 160 ms | R4·1 | not recomputed: the look-ahead favours the models, and they stayed null |
| **Selection on the future** | `quality_flagged` drops an episode if Binance trading paused for more than 2 s at any point before it closed; it removes 22.9 % of episodes and shifts levels (30 s maximum excursion 7.98 → 9.09 bp) | R4 | not recomputed; X1 and X2 flag an episode only if the quote stops updating for more than 60 s |
| **Exit price** | exits at the last print, not the best bid | R4·1 | bid–ask median 0.03 bp, p99 0.89 — bound, not repaired |
| **Detector labels** `DEF-F017` | features over a 10 s bucket, label from the bucket start | the breach-detector work behind R4·2 | repaired: decision moved to bucket close, AUC 0.991 → 0.988 |

### Vendor and data limits

| defect | what it does | results on it | treatment |
|---|---|---|---|
| **100 ms book** `DEF-F032`, `DEF-F020` | CoinAPI resells Binance's `@depth@100ms`; its BBO is the top of the same frames, so the two tapes are one | R3·2, R4 (setup 6) | bound: a null through a 100 ms filter cannot tell absent signal from signal under 100 ms |
| **Liquidation stamp** `DEF-F035` | CoinAPI's `time_open` trails the trade by more than 1 s on 20.6 % of bars | R1·1 background split, R5·1, R5·2 | recomputed from the trade time `T` |
| **Zero OI snapshots** `DEF-F036` | zero readings in the `metrics` archive | R5·3, R5·4 | dropped before differencing |
| **Taker side** `DEF-F033` | the aggressor side was dropped at ingest | — | recovered into `binance_trades_signed` |

---

<sub>
Sources: the evidence lines under each rung point to run folders in <code>artifacts/</code> and chunks in <code>db/source/</code>; the audit behind this edition is <code>db/handoff/review-rev8-audit-2026-09-13.md</code>.<br>
External: Wu, Sui, Thiery &amp; Pai, <a href="https://arxiv.org/abs/2507.13023">arXiv:2507.13023</a>; Cheng, Deng, Wang &amp; Yu, <em>Liquidation, leverage and optimal margin in bitcoin futures markets</em>, Applied Economics 53 (2021), <a href="https://arxiv.org/abs/2102.04591">arXiv:2102.04591</a>.<br>
Figures are drawn to scale from the result files named in their captions; no plotted value is typed by hand.<br>
Holdout: 2025-09 onward sealed and unread. R2's fold 2 was scored once.
</sub>
