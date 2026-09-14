# Lix Assistant

Lix Assistant automates supported Limbus Company tasks in a focused Windows game window.

The `architecture-refactor` branch is the clean Workflow 2.0 reconstruction. It intentionally does not contain or remain compatible with the legacy global node registry, JSON node graph, or manual Pipeline runtime. The former branch remains available for historical reference and rollback.

## Current status

- Stage 1 product and Agent boundaries: accepted.
- Stage 2 Workflow and deterministic-execution architecture: accepted.
- Stage 2 implementation: not started.
- Stage 3 Agent and Capability Expansion requirements: next for discussion.

Start with:

- [Domain language](CONTEXT.md)
- [Reconstruction plan](docs/reconstruction-plan.md)
- [Stage 2 implementation slices](docs/stage-2-implementation-slices.md)
- [Architecture decisions](docs/adr/)

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
