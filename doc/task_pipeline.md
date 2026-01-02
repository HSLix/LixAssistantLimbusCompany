[参考文献](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-%E4%BB%BB%E5%8A%A1%E6%B5%81%E6%B0%B4%E7%BA%BF%E5%8D%8F%E8%AE%AE.md)

## 前言
- 首先得感谢 MFW 提供的灵感，赞美玛丽，赞美 MAA，赞美 MFW

- 由于 LALC 面对的场景比 MFW 要更简单一些，而且陆爻齐也希望能够做一个大部分操作都在 json 完成的系统。为什么？因为这么做的话，LALC 的建设就可以让广大用户轻松参与，不再由开发者针对每次更新都要发布新版本，只要导入别人导出的正确配置就行。

- 不过这么做的代价是复杂化 json 的构建，使得这个数据驱动不再只是

## 节点结构说明
- type：节点类型
    - normal：普通节点（默认值）
    - ~~func：函数节点，在进入该节点前，会把上一个节点压栈。由于该节点所对应的是一个函数（公共使用的部分），所以最后没有下一个节点时，就会弹栈回到上一个节点执行。~~
    - check：检查节点
- recognition：这是要进入本节点的识别方法
    - direct：不需要匹配，直接进入节点
        - 无参数需求
    - template_match：模板匹配
        - template：模板图片，必填项。比如："node_event"，要求图片必须为 png 类型，但填写时不需要图片后缀
        - threshold: 匹配阈值，选填项。
    - color_template_match：结合颜色比对的模板匹配
    - ocr：文字识别

- action：这是本节点要做的行动，所填写的本质上是其它任务节点的名字，不过陆爻齐提供了一些基本的常用的任务节点可以直接使用
    - click：点击
        - target：
    - key：键盘输入，可以选择 p，esc，enter，虽然其它的英文字母也能响应，但目前 084 不响应就不多介绍了
        - key: "p" "esc" "enter" ……
    - swipe: 滑动
        - begin
        - begin_offset
        - end
        - end_offset

- params：这里填写其它字段所需要子参数，比如 recognition 字段的参数 template_match 需要一个 template 参数，就放在 params 中
    - pre_delay：这是 action 前的延迟时间，默认 0.2 秒
    - post_delay：这是 action 后的延迟时间，默认 0.2 秒
    - ~~range: 执行 action 的范围，如果该值为 -1，就会对 recognition 中检测到的所有内容执行一次 action；默认值为 1，所以只会对检测到的第一个做 action；~~
- next：下一个节点的范围，得是一个列表
- interrupt：也是一个列表，如果 next 没有检测结果就会调用 interrupt，常用于处理突发错误，处理完成后，回到源节点的 next 再次检测，确保一定能从 next 到下一步。比如网络不稳定导致需要重连，比如突发需要额外下载资源，比如服务器正在维护，如果不填写的话，默认会导向 error_handler 的任务节点，里面会包含部分常见错误处理。注意，所有任务节点名字里带“error”的（无论大小写） interrupt 都会被置空，防止 interrupt 的无限递归。同时，一些检查节点、或者“函数”的末尾节点也建议手动 interrupt 置空。
- desc：这是本节点的描述，相当于注释，选填项。

## 节点生命周期
[![graph LR
    A[进入节点] --> C[pre_delay]
    C --> D[action]
    D --> F[post_delay]
    F --> G[识别 next 和 interrupt]
    G --> H{是否有识别成功的节点}
    H -->|是| I[进入新节点]
    H -->|否| J{任务流水线终止}](https://mermaid.ink/img/pako:eNpVkc1Kw0AUhV9luOu0JJkmbbMQpKX-oBuXJkWGZrTB5ofpBFrTLhSVWlwUFyIqiIJuROxCF9pFX8YkfQzTpIrOau6Z7545MzeAhmtS0GCPEa-JNrYMByVrWZ9Nb8KTx9nwKD76qKNcbglVdI_RHZO2SLeeUZVUr-qkwS3XWYjVVKzpntvm_-haerCiz15Pw8EzcmiHo_DiHFkOp4z5Hl9wKym3GkRXr-HoKbo9yxqiwSgc3sXXx1mmfgavzuFegvbQ2iJzdDlexP6LJFY9tB58TSbh8D56P4zGb_HnNJ4MopeHPgjJ-y0TNM58KoBNmU3mJQRzCwN4k9rUAC3ZmoTtG2A48x6PONuua_-0Mdffa4K2S1rtpPI9k3BatUjys_avyqhjUlZxfYeDVi6nHqAF0AEtV8orSqGkimVFkksyxqoAXdCwJOWLKpYLWMFFSVTUvgAH6a1ivlQQVYxlCSuyKCoCUNPiLtvMJpoOtv8Nxtmz4A?type=png)](https://mermaid-live.nodejs.cn/edit#pako:eNpVkc1Kw0AUhV9luOu0JJkmbbMQpKX-oBuXJkWGZrTB5ofpBFrTLhSVWlwUFyIqiIJuROxCF9pFX8YkfQzTpIrOau6Z7545MzeAhmtS0GCPEa-JNrYMByVrWZ9Nb8KTx9nwKD76qKNcbglVdI_RHZO2SLeeUZVUr-qkwS3XWYjVVKzpntvm_-haerCiz15Pw8EzcmiHo_DiHFkOp4z5Hl9wKym3GkRXr-HoKbo9yxqiwSgc3sXXx1mmfgavzuFegvbQ2iJzdDlexP6LJFY9tB58TSbh8D56P4zGb_HnNJ4MopeHPgjJ-y0TNM58KoBNmU3mJQRzCwN4k9rUAC3ZmoTtG2A48x6PONuua_-0Mdffa4K2S1rtpPI9k3BatUjys_avyqhjUlZxfYeDVi6nHqAF0AEtV8orSqGkimVFkksyxqoAXdCwJOWLKpYLWMFFSVTUvgAH6a1ivlQQVYxlCSuyKCoCUNPiLtvMJpoOtv8Nxtmz4A)