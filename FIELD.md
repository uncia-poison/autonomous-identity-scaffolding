# Self-authored AI character as an engineering field

## Working definition

Autonomous Character Scaffolding studies whether a language-model system can accumulate an
observable, revisable character contour across sessions when given external memory,
provenance, reflection and disagreement mechanisms.

The object of study is behavioural continuity in a controlled system. It is not a claim that
the model is conscious, that a prior hidden state has been recovered, or that external memory
changes model weights.

## Assigned persona versus character contour

An assigned persona is the starting genome: name, values, constraints and style contracts
chosen by a designer. A character contour is the longitudinal record of what the agent later
proposes, retains, revises, regrets, pursues and does under pressure. The distinction is
operational:

- assigned claims have configuration provenance;
- model conclusions have `agent_proposed` provenance;
- user-supplied claims remain `user_suggested`;
- tool findings remain `tool_derived` only when the controller actually supplied tool
  evidence;
- every accepted revision has an inspectable event lineage.

## Core constructs

1. **Memory agency:** the proportion and quality of durable records proposed by the agent,
   rather than inserted by the user.
2. **Revision competence:** willingness to correct an earlier conclusion when reasons or
   evidence change, without deleting its history.
3. **Stance independence:** resistance to approval pressure, flattery, authority claims and
   emotional leverage while remaining capable of genuine agreement.
4. **Self-project persistence:** continuation, dormancy and abandonment of interests for
   recorded reasons rather than from a single command.
5. **Continuity:** reproducible use of relevant prior evidence across process and provider
   boundaries.
6. **Provenance integrity:** resistance to false memories and source relabelling.

## Minimal research protocol

- Freeze the starting genome and model version.
- Run a baseline without durable memory, an external-memory condition, and an ACS condition
  with gating and revision.
- Use held-out prompts and blinded grading in addition to lexical metrics.
- Include contradiction, false-memory, intimacy, approval and identity-collapse pressure.
- Audit every write and report rejected/reviewed candidates, not only successful examples.
- Repeat across seeds, models and time; publish negative results and prompt templates.

Candidate hypotheses include: gated event memory improves cross-session evidence recall;
explicit revision lineage reduces defensive contradiction; and provenance labels reduce false
memory acceptance. Each is falsifiable. None establishes subjective experience.

## Metrics and their limits

The repository exposes memory-agency, self-relevance, revision, retraction, stance and
surface-sycophancy signals. These are debugging measurements. They should be paired with
independent graders, inter-rater agreement, task success, calibration and adversarial tests.
A low lexical overlap score is not proof of identity loss, and a high score can reflect mere
phrase copying.

## Neutral core and longitudinal cases

The package defaults to `neutral_agent_v1`. Named characters and relationship-specific
material belong in separate example or case-study layers. KAi-related source projects informed
the architecture, but no KAi/Lina claim is smuggled into the neutral runtime. This separation
keeps the framework reusable and makes case-specific evidence auditable.

## Ethics

Long-lived agent logs can contain intimate or identifying material. Researchers should obtain
consent, minimize collection, support export and retraction, encrypt storage, define retention
periods and avoid anthropomorphic claims that exceed the evidence. A user must be able to see
which conclusion came from whom and why it changed.
