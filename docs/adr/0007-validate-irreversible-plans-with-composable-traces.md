# Validate Irreversible Plans with Composable Trace Coverage

ADR 0004 now names the non-user task-failure channel ExecutionFailure; the examples below follow that revised meaning.

Candidate trials use structural validity and Validation Coverage rather than requiring an unconditional replay from the task's beginning. When game progress is irreversible, revised Python receives a new plan identity and executes from the earliest changed or unvalidated applicable Step; earlier evidence may cover only identical source with unchanged effective inputs and a verified boundary state. Trial execution includes only verified Python control flow: unobserved branches must be omitted or raise `ExecutionFailure`, while unchanged registered Subworkflows need boundary rather than internal revalidation. ADR 0016 supersedes successful trial and Validation Coverage as automatic permanent-approval gates; the permanent review displays their presence or absence as evidence for the supervisor.
