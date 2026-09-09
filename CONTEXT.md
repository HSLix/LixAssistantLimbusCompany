# Lix Assistant

Lix Assistant automates a Windows-native Unity game window while allowing the user to continue using the desktop independently.

## Language

**Target Window**:
The Windows desktop window owned by the Unity game that Lix Assistant observes and operates.
_Avoid_: Emulator, virtual device

**Background Operation**:
The preferred interaction mode in which the Target Window may remain minimized while Lix Assistant observes and operates it without taking over the user's mouse or keyboard.
_Avoid_: Headless operation, foreground simulation

**Foreground Operation**:
The fallback interaction mode in which the Target Window is restored and Lix Assistant operates it with mouse and keyboard actions that remain reliable when other windows overlap it.
_Avoid_: Background operation
