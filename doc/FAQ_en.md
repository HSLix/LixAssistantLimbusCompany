# FAQ
---
en | [中文版](FAQ_cn.md)
---
- Q: Does LALC have to occupy the mouse?
- A: Yes, so it's not recommended to use the device for other tasks while LALC is running. Consider using a virtual machine or remote desktop instead. Refer to this [article](https://www.bilibili.com/opus/805995851989123075) for details.
---
- Q: Does screen scaling affect LALC?
- A: **150%** scaling is the most suitable for LALC. While nearby resolutions can work, the performance may be less stable.
---
- Q: What should I do if LALC runs 异常 (abnormally), freezes, or shows error pop-ups?
- A:
1. Save the log files from the log folder in LALC's installation directory (for the current day).
2. Save the recordings generated during runtime.
3. Submit an Issue following the Report Bug template requirements with your log file, including debug, info, warning, and the video, which could be shown conveniently on [dicord](https://discord.gg/bVzCuBU4bC).
---
- Q: I get an error like "UnicodeEncodeError: 'charmap' codec can't encode characters……" when opening LALC. What should I do?
- A: Refer to the [solution](https://github.com/HSLix/LixAssistantLimbusCompany/issues/26) provided by 陆爻齐 (Lu Yaoqi) in this Issue.
---
- Q:After using LALC, the memory has been lost for some reason, what's wrong?
- A:It's probably because the video files are not cleaned up in time after recording, please open the recording folder from the ‘Settings’ interface to clean up the folder regularly, or disable the function of recording. Please note that screen recording is very important for troubleshooting programme errors. According to the past experience, it is **often difficult** to fix the errors that occurred after losing the screen recording just by the log file.
---
- Q:Why is it that I've been using LALC to fully automate the Mirror for a long time, but in the end I find that it doesn't clear?
- A:It's most likely because every time when you entry the Mirror, it fails, and then LALC will choose to give up the rewarding. Please check the screen recording and logs to make sure. If this is not the case, please refer to the FAQ for bug feedback.
---
- Q:LALC can not run with the error report like the [Issue](https://github.com/HSLix/LixAssistantLimbusCompany/issues/155).
- A:Make sure that the path of LALC is all English.