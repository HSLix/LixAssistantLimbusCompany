---
status: accepted
---

# Use one focused interaction mode

LALC will operate Limbus Company only during a Focused Automation Session: the game is restored, owns real Windows foreground focus, receives cursor-free mouse input, and receives ordinary foreground keyboard input. Although Cursor-Assisted Background Operation can click the unfocused and occluded game reliably, it temporarily seizes the user's mouse and still has no safe background keyboard path; keeping both modes would add complexity without preserving independent desktop use.

## Considered options

- **Focused Automation Session — accepted.** A single real focus state gives Unity consistent mouse and keyboard semantics. The user yields desktop interaction for the duration of automation.
- **Cursor-Assisted Background Operation — rejected.** Fake activation plus temporary physical-cursor alignment works for mouse input whether the game is visible or occluded, but interrupts the user's cursor and cannot provide a safe matching keyboard implementation.
- **Fully independent background operation — rejected.** Message-only mouse input is ignored, message-only keyboard input waits for focus, unfocused synthetic touch waits for focus, and the managed-key experiment corrupts the game's interaction state until restart.

## Consequences

The input layer and future state graph may assume that the Target Window is restored and foreground-focused. Losing focus pauses input or triggers focus reacquisition; minimized and independently usable desktop operation are outside the supported boundary.
