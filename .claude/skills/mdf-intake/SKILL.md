---
name: mdf-intake
description: Turn a machine specification document (or a conversation) into an MDF project - quantified, sourced requirements, a process definition and a list of open questions - before any design work. Use when a new machine or station is introduced, or a spec document changes.
---
# Spec intake  [TIER-A]

Most special-machine projects that fail were under-specified at the start. Intake makes every requirement
quantified, sourced and testable, and turns every gap into a question for the chief engineer **before**
design starts. Do not design during intake.

## Steps
1. **Read the whole spec** (docx/pdf/notes). Note document id, revision and date.
2. **Extract every requirement** into `intake/requirements_draft.yaml` (requirements schema), each with
   `source: "<doc> §<section>"` and the original wording in `rationale`. One requirement per testable statement.
3. **Quantify.** Replace every unquantified word ("fast", "accurate", "robust", "easy to change over")
   with a number + tolerance + condition, or raise a question. Never invent the number.
4. **Classify** each (process, performance, mechanical, controls, electrical, safety, maintenance, manufacturing)
   and choose its verification (check / test / review).
5. **Walk the checklist** (`templates/SPEC_CHECKLIST.md`); every unanswered item becomes a question.
6. **Find conflicts** (speed vs. accuracy, format range vs. changeover time, budget vs. scope) and list them.
7. **Draft the process** (skill `mdf-process`): product states, ports, tolerances, held-at-every-instant.
8. **Write `intake/QUESTIONS.md`**: numbered, grouped, each saying why it matters and what it blocks.
   Ask the fewest questions that unblock the most design.
9. **Scaffold** the project: `PYTHONPATH=tools python3 -m mdf new machines/<machine>/stations/<station>`,
   then move the approved requirements in. Run `make verify`; run `make lock` only after the chief engineer
   approves the requirements and check definitions.

## Output to the chief engineer
- requirement count by category, how many quantified vs. pending
- the questions (most blocking first)
- conflicts found
- anything in the spec that looks like a solution rather than a requirement ("use pneumatic cylinder X"):
  record it as a constraint with its reason, or ask whether it is really required
