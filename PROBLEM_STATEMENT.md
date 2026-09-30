# Cube Buildathon · 02 · Prep Manager

**Commerce Context stream · Round 2 · Individual Build**

> Five agents, one unit, one record that follows it.
> A physical product arrives, gets prepped, gets shipped, comes back. At every step a person makes a fast judgment that nobody records. **You build the agent that makes one of those judgments, and leaves proof.**

**New here? Read these first:**

1. [`GITHUB-GUIDE.md`](GITHUB-GUIDE.md) explains how to fork the repository, set it up, build and push your work.
2. [`RULES.md`](RULES.md) covers the repository and engineering rules.

---

## Your problem statement: Prep Manager

|                              |                                                                      |
| ---------------------------- | -------------------------------------------------------------------- |
| **Position in the chain**    | Step 2 of 5. Inbound to Amazon.                                      |
| **Customer**                 | Prep center owner, or self-prepping seller                           |
| **What gets recorded**       | Compliance proof                                                     |
| **Who consumes your output** | Recovery Manager (disputed prep fees, lost or damaged inbound units) |

A unit is prepped for inbound shipment to Amazon. If the prep is wrong, Amazon charges a defect fee, and it arrives six weeks later attached to a shipment nobody can remember. The prep center has a work order saying what they were supposed to do, and their word that they did it. That is not evidence, and a meaningful share of those fees may be for defects that did not exist when the unit left the building.

**What the agent checks, from photographs of the prepped unit:**

* Polybag present and correctly sealed
* Suffocation warning present and legible, not obscured by the fold
* FNSKU label flat, not on a seam, curve or edge
* Original manufacturer barcode covered
* Expiry date still legible after wrapping
* Required handling marks: fragile, liquid, this way up

> **Look the rules up.** Amazon publishes its prep requirements. Do not infer them from examples and do not let a model guess. In a compliance check backed by an evidence record, "we retrieved something similar" is not a defensible answer.

> **The hard constraint.** This touches every unit, not one in five. A prep center works on $0.40 to $1.10 per unit. Your cost per check has to live inside that.

### The chain you are part of

```text
 Supplier delivery      Inbound to Amazon     Outbound to buyer     Customer return        Money back
 ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
 │ 01 Receiving │ ───▶ │ 02 Prep      │ ───▶ │ 03 Pack      │ ───▶ │ 04 Returns   │      │ 05 Recovery  │
 │ condition on │      │ compliance   │      │ contents at  │      │ condition &  │      │ reads all    │
 │ arrival      │      │ proof        │      │ seal         │      │ disposition  │      │ four → claim │
 └──────┬───────┘      └──────┬───────┘      └──────┬───────┘      └──────┬───────┘      └──────▲───────┘
        └─────────────────────┴─────────────────────┴─────────────────────┴─────────────────────┘
```

The first four are the same machine: a camera, a model, and a decision bound to a record. What changes is the ruleset, the buyer and the moment. The fifth has no camera. It turns the other four's records into a claim.

Your output has to be usable by another pod. That's deliberate, and it's scored.

---

## Reference data

`data/` holds a **dummy** CSV for reference while you design and build. Its columns and meanings are listed in [`data/README.md`](data/README.md).

**The data is synthetic.** The SKUs, ASINs, FNSKUs, orders, suppliers, operators and amounts are all invented. The requirement flags and fee amounts are **not** Amazon's real rules or fees. Engineering rule 5 applies: look the authoritative rule up. The `photo_refs` paths are placeholders, and no images ship with this repo. Your fixtures and eval set are yours to capture.

All five buildathon repos share the same `unit_id` values (`UNIT-0001` … `UNIT-0100`). You can follow one unit from receiving through recovery, the same way the real records will be joined. In the sample, each unit takes one route: **FBA** (prep, then Amazon ships it and charges fees) or **merchant-fulfilled / 3PL** (the seller packs it). So a unit has a Prep record or a Pack record, never both.

---

## How this works

You have a defined problem statement, supporting domain information and an engineering repository to build from. Real products are built backwards from the customer and forwards through the evidence. Understand the customer and operational workflow before writing code, then build and measure whether the solution works.

Every design decision should be testable. A wrong assumption caught early costs less than the same assumption discovered after implementation. You are assessed on that as much as on running software.

### What you're given

* This problem statement
* A domain brief covering the real economics, fee structures and what a working day in a warehouse looks like *(shared by the organisers)*
* The engineering rules in [`RULES.md`](RULES.md)
* Repository data and supporting resources
* One fully worked package for Returns Manager (customer letter, PR/FAQ, one-pager) as a reference for the standard expected. **Read it. Don't copy it.**

### What you produce

Build your solution in **your own GitHub fork**.

Your final Round 2 submission should include:

* A working Prep Manager
* A `README.md` explaining your solution, setup, assumptions and limitations
* An `ARCHITECTURE.md`
* An eval report/results with numbers and named failure modes
* A working demo/video
* A deployment URL, where applicable
* Your mandatory LinkedIn post URL

## Build and submission flow

```text
Understand
    ↓
Build
    ↓
Test
    ↓
Evaluate
    ↓
Document
    ↓
Demo / Deploy
    ↓
Submit
```

Round 2 is an **individual build**.

The official build phase begins on **25 September 2026 at 9:00 AM IST**.

Submissions open from **27 September 2026**.

The final submission deadline is **1 October 2026 at 6:00 PM IST**.

The submission form closes permanently at the deadline. **There is no resubmission.**

All code commits forming your Round 2 submission must be made during the authorised build phase. Do not continue making Round 2 code changes after the build phase ends.

## What we're being straight with you about

* **The core assumption is untested.** Nobody knows yet whether vision models can identify products and verify prep requirements reliably across long-tail catalogues without per-SKU training. Finding out that it doesn't hold, and documenting that clearly, counts as a useful outcome.
* **Nobody has spoken to a customer yet.** If you can get a real prep center or seller on a call, ask them to rank the five problems by urgency. Don't ask whether they'd buy what you're building.
* **The background documents disagree in places.** A contradiction is a finding. Raise it as an Issue labelled `finding`.

---

## Evaluation

Your Round 2 submission is evaluated out of **100 points**:

| Criterion                                    |  Points |
| -------------------------------------------- | ------: |
| Problem Understanding & Solution Relevance   |  **15** |
| Agent Functionality & Decision Quality       |  **25** |
| Evaluation, Accuracy & Uncertainty Handling  |  **25** |
| Evidence, Traceability & Engineering Quality |  **20** |
| UX, Demo & Documentation                     |  **15** |
| **TOTAL**                                    | **100** |

For the vision-based portions of the Prep Manager, use an appropriate unseen/held-out evaluation set and report your methodology, results, false positives, false negatives, `UNCERTAIN` cases and failure modes.

---

## Evidence and decision traceability

Your Prep Manager should leave evidence behind for its decisions.

At minimum, the workflow should make it possible to understand:

```text
What was being prepped?
        ↓
What requirements were checked?
        ↓
What did the agent observe?
        ↓
What verdict was produced?
        ↓
Why?
```

Use the official evidence contract provided by the organisers as the baseline for interoperability with the other Managers.

---

## PASS · FAIL · UNCERTAIN

For individual checks:

* **PASS** — the evidence supports the condition.
* **FAIL** — the evidence shows the condition is not met.
* **UNCERTAIN** — the evidence is insufficient for a reliable judgment.

`UNCERTAIN` is not simply a low-confidence PASS.

---

*CUBE Buildathon · Commerce Context*
