[参考文献](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-%E4%BB%BB%E5%8A%A1%E6%B5%81%E6%B0%B4%E7%BA%BF%E5%8D%8F%E8%AE%AE.md)

## 属性字段
recognition : string
识别算法类型。可选，默认 DirectHit 。
可选的值：DirectHit | TemplateMatch | FeatureMatch 

action: string
执行的动作。可选，默认 DoNothing 。
可选的值：DoNothing | Click | Swipe | Key | StopTask | Log | Custom
Custom 需要补充字段 custom_name: string，然后自定义活动得带有这个名字

action_rest: int
执行动作之间的间隔时间，可选，默认 0。
暂时专属于 click 和 key

action_count: int
重复执行动作的次数，可选，默认 1。
目前仅对 Click 和 Key 行动生效。

next : string | list<string, >
接下来要执行的节点列表。可选，默认空。
按顺序识别 next 中的每个节点，只执行第一个识别到的。

interrupt : string | list<string, >
next 中全部未识别到时的候补节点列表，会执行类似中断操作。可选，默认空。
若 next 中的节点全部未识别到，则会按序识别该中断列表中的每个节点，并执行第一个识别到的。在后续节点全部执行完成后，重新跳转到该节点来再次尝试识别。
例如: A: { next: [B, C], interrupt: [D, E] }
当 B, C 未识别到而识别到 D 时，会去完整的执行 D 及 D.next。但当 D 的流水线完全执行完毕后。会再次回到节点 A，继续尝试识别 B, C, D, E 。
该字段多用于异常处理，例如 D 是识别 “网络断开提示框”，在点击确认并等待网络连接成功后，继续之前的节点流程。

~~on_error : string | list<string, >~~
~~当动作执行失败后，接下来会执行该列表中的节点。可选，默认空。~~

enabled: bool
是否启用该 node。可选，默认 true 。
若为 false，其他 node 的 next 列表中的该 node 会被跳过，既不会被识别也不会被执行。

pre_delay: uint
每次执行动作前的延迟，秒。可选，默认 0.2 。
推荐尽可能增加中间过程节点，少用延迟，不然既慢还不稳定。

post_delay: uint
每次执行动作后的延迟，秒。可选，默认 0.2 。
推荐尽可能增加中间过程节点，少用延迟，不然既慢还不稳定。

pre_wait_freezes: uint 
识别到 到 执行动作前，等待画面不动了的时间，秒。可选，默认 0 ，即不等待。
连续 pre_wait_freezes 毫秒 画面 没有较大变化 才会退出动作。
若为 object，可设置更多参数，详见 等待画面静止。
具体的顺序为 pre_wait_freezes - pre_delay - action - post_wait_freezes - post_delay 。

post_wait_freezes: uint 
行动动作后 到 识别 next，等待画面不动了的时间，秒。可选，默认 0 ，即不等待。
其余逻辑同 pre_wait_freezes。

log_level: str
是日志记录等级，可选，默认DEBUG
可以是 INFO, WARNING, ERROR, CRITICAL


## 算法类型
### DirectHit
直接命中，即不进行识别，直接执行动作。

### TemplateMatch
模板匹配，即“找图”。

该算法属性需额外部分字段：

recognize_area: array<int, 4> 
识别区域坐标。可选，默认全屏 [0, 0, 0, 0]。
array<int, 4>: 识别区域坐标，[left, top, weigh, heigh] 。

template: string 
模板图片路径，暂时默认在 resource/template，所以直接填入对应图片完整名字即可（包括后缀名.png）

threshold: double 
模板匹配阈值。可选，默认 0.8 。

### ColorMatch
颜色匹配，也就是“找色”。

该算法属性需额外部分字段：

recognize_area: array<int, 4> 
识别区域坐标。可选，默认全屏 [0, 0, 0, 0]。
array<int, 4>: 识别区域坐标，[left, top, weigh, heigh] 。

color_point: array<int, 2>
坐标，必选，相对 recognize_area 的左上角而言。

lower：int
颜色下限值。可选。默认 0.

upper：int
颜色上限值。可选。默认 255.


## 动作类型
DoNothing
什么都不做。

### Click
点击。

该动作属性需额外部分字段：

target: true | array<int, 2> ~~| array<array<int, 2>, *>~~
点击的位置。可选，默认 true 。
true: 点击本节点中刚刚识别到的目标（即点击自身）。
array<int, 2>: 点击固定坐标
~~array<array<int, 2>, *>: 点击一系列固定坐标~~

target_offset: array<int, 2>
在 target 的基础上额外移动再点击。可选，默认 [0, 0] 。



### Swipe
线性滑动。

该动作属性需额外部分字段：

begin: true | array<int, 2>
滑动起点。可选，默认 true 。值同上述 Click.target 。

begin_offset: array<int, 2>
在 begin 的基础上额外移动再作为起点。可选，默认 [0, 0] 。

end: true | array<int, 2>
滑动终点。可选，默认 true 。值同上述 Click.target 。

end_offset: array<int, 2>
在 end 的基础上额外移动再作为终点。可选，默认 [0, 0] 。

duration: uint
滑动持续时间，单位秒。可选，默认 0.2 。


### Key
按键。

key: string | list<string>
要按的键，仅支持 p, enter, esc。

### Checkpoint
~~不太好用，后续再改~~
本次任务结束检查点，会根据Control Unit传入的任务已执行次数。

target_task_count_name: string 
必要字段
当前任务计数名字，用于task自己核对次数是否满足，没满足就把next的部分换成current_task_name,满足了就设置next为next_task_name

current_task_name: string
必要字段
当前任务名字，不满足检查要求时，就返回到该任务。

next_task_name: string
必要字段
满足次数后，要执行的下一个任务名字。

