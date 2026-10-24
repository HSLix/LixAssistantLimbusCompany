import { access, readFile, realpath, writeFile } from "node:fs/promises";
import { writeSync } from "node:fs";
import { isAbsolute, join, relative, resolve } from "node:path";
import { createReadTool, createEditTool } from "@earendil-works/pi-coding-agent";
import { openAICompletionsApi, Type } from "@earendil-works/pi-ai";

// 每次实际文件访问都检查解析后的路径，不能只检查模型提供的字符串。
export async function checkedPath(root: string, path: string) {
  const target = await realpath(resolve(root, path));
  const rel = relative(root, target);
  if (rel === ".." || rel.startsWith("../") || rel.startsWith("..\\") || isAbsolute(rel)) {
    throw new Error("Source read outside allowed directory");
  }
  return target;
}

export default async function (pi) {
  const root = await realpath(process.env.LALC_PI_SOURCE_ROOT!);
  const repairMode = process.env.LALC_PI_REPAIR_FILES !== undefined;
  const repairTargets: string[] = JSON.parse(process.env.LALC_PI_REPAIR_FILES || "[]");
  const history = process.env.LALC_PI_HISTORY ? JSON.parse(await readFile(process.env.LALC_PI_HISTORY, "utf8")) : [];
  const inputImages = process.env.LALC_PI_INPUT_IMAGES
    ? JSON.parse(await readFile(process.env.LALC_PI_INPUT_IMAGES, "utf8")) : [];
  pi.on("context", async event => {
    const messages = [...history, ...event.messages];
    if (inputImages.length) {
      // RPC 图片预处理会转码或丢弃部分格式；原图只经 context hook 注入。
      const userIndex = event.messages.findIndex(message => message.role === "user");
      if (userIndex < 0) throw new Error("Original image message not found");
      const index = history.length + userIndex;
      messages[index] = { ...messages[index], content: [
        { type: "text", text: process.env.LALC_PI_INPUT_MESSAGE }, ...inputImages] };
    }
    return { messages };
  });
  pi.on("before_agent_start", async event => {
    // 格式纠正只重发最终回答，禁止重新调用工具或重复修改候选。
    if (repairMode && event.messageType === "user" && event.prompt.startsWith("LALC_FINAL_FORMAT_CORRECTION\n")) {
      pi.setActiveTools([]);
    }
  });
  const preflight = process.env.LALC_PI_PREFLIGHT === "1";
  const repairTools = ["read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
                       "action_contracts", "game_screenshot", "crop_asset", "add_component", "add_recovery_rule"];
  const limit = Number(process.env.LALC_PI_MAX_REQUESTS);
  let requests = Number(process.env.LALC_PI_REQUESTS_USED || 0);
  const conversationRound = process.env.LALC_PI_CONVERSATION_ROUND;
  const roundLimit = Number(process.env.LALC_PI_ROUND_REQUEST_LIMIT || limit);
  const api = openAICompletionsApi();
  // 新版 pi 重定向 console 和 stdout.write；协议事件显式写入原始 stdout 描述符。
  const emit = (type, fields) => writeSync(1, JSON.stringify({ type, ...fields }) + "\n");
  pi.registerProvider("lalc-probe", {
    baseUrl: process.env.LALC_PI_BASE_URL,
    apiKey: "$LALC_PI_API_KEY",
    api: "openai-completions",
    models: [{
      id: process.env.LALC_PI_MODEL,
      name: process.env.LALC_PI_MODEL,
      reasoning: false,
      input: ["text", "image"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 65536,
      // pi 必须有数值型模型元数据；实际请求在下方移除客户端输出预算。
      maxTokens: 0,
    }],
    streamSimple(model, context, options) {
      return api.streamSimple(model, context, {
        ...options,
        maxRetries: 0,
        async onPayload(payload, model) {
          payload = options?.onPayload ? (await options.onPayload(payload, model)) ?? payload : payload;
          // pi 会按模型元数据补预算；最终发送前移除，明确使用服务端默认值。
          delete payload.max_tokens;
          delete payload.max_completion_tokens;
          delete payload.max_output_tokens;
          // 扩展事件中的异常会被 pi 捕获；上限必须在客户端回调里拒绝发送。
          if (requests >= limit) throw new Error("LALC request limit reached");
          requests++;
          if (conversationRound) {
            // 在最终载荷注入当前额度，避免 SDK 丢弃上下文字段；不改长期历史。
            const budget = `当前对话第 ${conversationRound} 轮；本轮模型请求第 ${requests}/${roundLimit} 次（包含本次，还可请求 ${Math.max(0, roundLimit - requests)} 次）。`
              + "每条用户消息独立计数，连接预检和格式纠正均计入。最后一次请求必须给出最终回答，停止调用工具；达到上限后必须停止，不得继续请求。";
            const system = payload.messages.find(message => message.role === "system" || message.role === "developer");
            if (system) system.content += "\n\n" + budget;
            else payload.messages.unshift({ role: "system", content: budget });
          }
          const shown = JSON.parse(JSON.stringify(payload, (_key, value) =>
            typeof value === "string" && value.startsWith("data:image/")
              ? `[image data URL: ${value.length} characters]` : value));
          if (process.env.LALC_PI_PAYLOAD_DIR) {
            // 大图请求不能与 RPC 事件并发倾倒到 stdout；独立保存完整载荷后只发送引用。
            const payloadPath = join(process.env.LALC_PI_PAYLOAD_DIR!, `request-${requests}.json`);
            const key = process.env.LALC_PI_API_KEY!;
            await writeFile(payloadPath, JSON.stringify(payload, (_name, value) =>
              typeof value === "string" && key !== "lalc-no-key" ? value.replaceAll(key, "[REDACTED]") : value));
            emit("lalc_request", { requests, request_limit: roundLimit, payload_path: payloadPath });
          } else {
            emit("lalc_request", { requests, request_limit: roundLimit, payload: shown });
          }
          return payload;
        },
      });
    },
  });
  const read = createReadTool(root, {
    operations: {
      access: async path => access(await checkedPath(root, path)),
      readFile: async path => readFile(await checkedPath(root, path)),
    },
  });
  pi.registerTool({
    ...read,
    async execute(id, params, signal, onUpdate) {
      // pi 的会话 cwd 会覆盖工厂 cwd，先固定为已检查的绝对路径。
      const path = await checkedPath(root, params.path);
      return read.execute(id, { ...params, path }, signal, onUpdate);
    },
  });
  if (repairMode) {
    const checkedEdit = async (path: string) => {
      const target = await checkedPath(root, path);
      if (relative(root, target).split(/[\\/]/).includes("plan.json") || !repairTargets.includes(target))
        throw new Error("Only existing Candidate files may be edited; plan.json is read-only");
      return target;
    };
    const edit = createEditTool(root, {
      operations: {
        access: async path => access(await checkedEdit(path)),
        readFile: async path => readFile(await checkedEdit(path)),
        writeFile: async (path, content) => writeFile(await checkedEdit(path), content),
      },
    });
    pi.registerTool({
      ...edit,
      async execute(id, params, signal, onUpdate) {
        const path = await checkedEdit(params.path);
        return edit.execute(id, { ...params, path }, signal, onUpdate);
      },
    });
    pi.registerTool({
      name: "validate", label: "Validate Developer Candidate",
      description: "Validate the complete current candidate Manifest and return actual errors. Does not run the workflow or publish.",
      parameters: Type.Object({}),
      async execute(_id, _params, _signal, _update, ctx) {
        // 复用 RPC 已有请求/响应通道，由 Python 宿主校验；不会向用户交互提问。
        const value = await ctx.ui.input("lalc.validate:" + _id);
        if (value === undefined) throw new Error("Validation cancelled");
        return { content: [{ type: "text", text: value }], details: JSON.parse(value) };
      },
    });
    const logicalName = Type.String({ description: "Complete Asset logical name, e.g. ui/claim" });
    const sourceParameters = Type.Object({ filename: Type.String(), logical_name: Type.String(), source: Type.String() });
    const tools = [
      { name: "add_component", description: "Create a new Candidate Python Component from complete source and register its logical name in components. No overwrite. The created file may be edited in this round.", parameters: sourceParameters },
      { name: "add_recovery_rule", description: "Create a new Candidate Recovery Rule from complete detect/recover source and register in recovery_rules. No overwrite. The created file may be edited in this round.", parameters: sourceParameters },
      { name: "asset_tree", description: "Read the global Asset logical-name text tree without loading images.",
        parameters: Type.Object({}) },
      { name: "asset_directory", description: "List all filenames and raw tag metadata for one complete Asset name; missing tags are reported without writing.",
        parameters: Type.Object({ logical_name: logicalName }) },
      { name: "asset_images", description: "View one or more actual Asset images by complete logical name and SHA-256. Any invalid item fails the whole batch.",
        parameters: Type.Object({ images: Type.Array(Type.Object({ logical_name: logicalName,
          sha256: Type.String({ pattern: "^[0-9a-f]{64}$" }) }), { minItems: 1 }) }) },
      { name: "action_contracts", description: "Read all registered Trusted Action classifications, signatures, return types and docstrings. Does not execute actions or expose implementation source.",
        parameters: Type.Object({}) },
      { name: "game_screenshot", description: "Restore and focus the unique game window, then return a fresh client-area image and dimensions. Unavailable on unsupported platforms; errors may be retried explicitly.",
        parameters: Type.Object({}) },
      { name: "crop_asset", description: "Restore and focus the unique game window and crop a NEW screenshot at client pixel coordinates. Add a new Asset or reuse an existing image and its original tags. No file import or game control.",
        parameters: Type.Object({ logical_name: logicalName,
          region: Type.Object({ x: Type.Integer(), y: Type.Integer(), width: Type.Integer(), height: Type.Integer() }),
          tags: Type.Optional(Type.Array(Type.String())) }) },
    ];
    for (const tool of tools) {
      pi.registerTool({ ...tool, label: tool.name,
        async execute(_id, params, _signal, _update, ctx) {
          // 图片走独立返回文件，避免大载荷与 RPC 事件竞争 stdout/stdin。
          const path = await ctx.ui.input("lalc.tool:" + JSON.stringify({ name: tool.name, arguments: params, tool_call_id: _id }));
          if (path === undefined) throw new Error("Repair tool cancelled");
          const result = JSON.parse(await readFile(path, "utf8"));
          if (!result.isError && (tool.name === "add_component" || tool.name === "add_recovery_rule")) {
            repairTargets.push(await checkedPath(root, result.details.filename));
          }
          return result;
        },
      });
    }
  }
  pi.on("session_start", () => {
    pi.setActiveTools(preflight ? [] : repairMode ? repairTools : ["read"]);
    emit("lalc_ready", { tools: pi.getActiveTools(), root, repairTargets,
                         availableTools: pi.getAllTools().map(tool => tool.name) });
  });
}
