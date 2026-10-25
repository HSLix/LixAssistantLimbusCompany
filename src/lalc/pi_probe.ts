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

// 只提取诊断字段，不序列化请求头、请求体或完整 SDK 错误对象。
export function transportCause(error, depth = 0) {
  if (depth > 5) return { message: "cause chain truncated" };
  if (!error || typeof error !== "object") return { message: String(error) };
  const result: Record<string, unknown> = {};
  for (const key of ["name", "message", "code", "errno", "syscall", "hostname", "address", "port"]) {
    if (["string", "number"].includes(typeof error[key])) result[key] = error[key];
  }
  if (error.cause) result.cause = transportCause(error.cause, depth + 1);
  if (Array.isArray(error.errors)) result.errors = error.errors.map(item => transportCause(item, depth + 1));
  return result;
}

export function diagnosticFetch(fetcher, report, requestNumber) {
  return async (input, init) => {
    const started = Date.now();
    const parsed = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const url = parsed.origin + parsed.pathname;
    const failed = (phase, error) => report({ requests: requestNumber(), url, phase,
      elapsed_ms: Date.now() - started, error: transportCause(error) });
    let response;
    try { response = await fetcher(input, init); }
    catch (error) { failed("connect", error); throw error; }
    if (!response.body) return response;
    const reader = response.body.getReader();
    const body = new ReadableStream({
      async pull(controller) {
        try {
          const { done, value } = await reader.read();
          if (done) controller.close(); else controller.enqueue(value);
        } catch (error) { failed("response_body", error); controller.error(error); }
      },
      cancel(reason) { return reader.cancel(reason); },
    });
    return new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers });
  };
}

export default async function (pi) {
  const root = await realpath(process.env.LALC_PI_SOURCE_ROOT!);
  const repairMode = process.env.LALC_PI_REPAIR_FILES !== undefined;
  const repairTargets: string[] = JSON.parse(process.env.LALC_PI_REPAIR_FILES || "[]");
  const history = process.env.LALC_PI_HISTORY ? JSON.parse(await readFile(process.env.LALC_PI_HISTORY, "utf8")) : [];
  const inputImages = process.env.LALC_PI_INPUT_IMAGES
    ? JSON.parse(await readFile(process.env.LALC_PI_INPUT_IMAGES, "utf8")) : [];
  const budgetHistory = [];
  let pendingBudget;
  let budgetPosition = 0;
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
    // 按原始消息位置重放通知，不改写已经发送的前缀。
    for (const { position, message } of [...budgetHistory].reverse()) {
      messages.splice(history.length + position, 0, message);
    }
    pendingBudget = undefined;
    if (conversationRound) {
      budgetPosition = event.messages.length;
      pendingBudget = { role: "user", timestamp: Date.now(), content: [{ type: "text", text:
        `LALC_REQUEST_BUDGET\n当前对话第 ${conversationRound} 轮；本轮模型请求第 ${requests + 1}/${roundLimit} 次（包含本次，还可请求 ${Math.max(0, roundLimit - requests - 1)} 次）。` }] };
      messages.push(pendingBudget);
    }
    return { messages };
  });
  pi.on("before_agent_start", async event => {
    // 格式纠正只重发最终回答，禁止重新调用工具或重复修改候选。
    if (repairMode && event.messageType === "user" && event.prompt.startsWith("LALC_FINAL_FORMAT_CORRECTION\n")) {
      pi.setActiveTools([]);
    }
    // 使用宿主原始提示词覆盖 pi 的自动工作目录段，工具声明仍由 pi 管理。
    return { systemPrompt: event.systemPromptOptions.customPrompt
      + "\n" + (repairMode ? "文件路径相对于 Candidate 根目录；已有文件列表由宿主提供。" : "文件路径相对于宿主指定的源码根目录。")
      + "\nLALC_REQUEST_BUDGET 是宿主额度通知，不是新用户轮次；历史通知原位保留，以最后一条为准。每条用户消息独立计数，连接预检和格式纠正均计入。最后一次请求必须给出最终回答，停止调用工具；达到上限后必须停止，不得继续请求。" };
  });
  const preflight = process.env.LALC_PI_PREFLIGHT === "1";
  const repairTools = ["read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
                       "action_contracts", "game_screenshot", "crop_asset", "add_component", "add_recovery_rule",
                       "publish", "trial_run", "list_runs", "read_run_log", "preview_crop", "remove_asset"];
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
      reasoning: process.env.LALC_PI_PROVIDER === "deepseek",
      ...(process.env.LALC_PI_PROVIDER === "deepseek" ? {
        compat: { thinkingFormat: "deepseek", supportsDeveloperRole: false,
                  supportsReasoningEffort: true, requiresReasoningContentOnAssistantMessages: true },
        thinkingLevelMap: { off: "off", low: "low", high: "high", max: "max" },
      } : {}),
      input: ["text", "image"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: process.env.LALC_PI_PROVIDER === "deepseek" ? 1000000 : 65536,
      // pi 必须有数值型模型元数据；实际请求在下方移除客户端输出预算。
      maxTokens: 0,
    }],
    streamSimple(model, context, options) {
      return api.streamSimple(model, context, {
        ...options,
        maxRetries: 0,
        fetch: diagnosticFetch(options?.fetch ?? globalThis.fetch, details => {
          const key = process.env.LALC_PI_API_KEY!;
          const clean = JSON.parse(JSON.stringify(details, (_name, value) =>
            typeof value === "string" && key !== "lalc-no-key" ? value.replaceAll(key, "[REDACTED]") : value));
          emit("lalc_transport_error", clean);
        }, () => requests),
        async onPayload(payload, model) {
          payload = options?.onPayload ? (await options.onPayload(payload, model)) ?? payload : payload;
          // pi 会按模型元数据补预算；最终发送前移除，明确使用服务端默认值。
          delete payload.max_tokens;
          delete payload.max_completion_tokens;
          delete payload.max_output_tokens;
          // 扩展事件中的异常会被 pi 捕获；上限必须在客户端回调里拒绝发送。
          if (requests >= limit) throw new Error("LALC request limit reached");
          requests++;
          if (pendingBudget) {
            budgetHistory.push({ position: budgetPosition, message: pendingBudget });
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
            emit("lalc_request", { requests, request_limit: roundLimit, payload_path: payloadPath, budget_message: pendingBudget });
          } else {
            emit("lalc_request", { requests, request_limit: roundLimit, payload: shown, budget_message: pendingBudget });
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
      { name: "publish", description: "Validate the complete Developer Candidate and save immutable hashed Component source and a new Manifest ID. Does not change Default or grant runtime permanent approval. Publish after edits before trial_run.", parameters: Type.Object({}) },
      { name: "trial_run", description: "Run an explicitly saved Manifest and wait for its actual result and Run ID. Modified Candidate code MUST be published first to enter the immutable hash index. Specify exactly one of logical_name or a Candidate-relative JSON plan_path. A rejected start has no Run ID; fix the cause before retrying. Results return within this round without resetting the request budget.",
        parameters: Type.Object({ manifest_id: Type.String(), logical_name: Type.Optional(Type.String()),
          inputs: Type.Optional(Type.Record(Type.String(), Type.Any())), plan_path: Type.Optional(Type.String()) }) },
      { name: "list_runs", description: "List retained Run IDs, newest first. No log content search.",
        parameters: Type.Object({ offset: Type.Optional(Type.Integer({ minimum: 0 })), limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200 })) }) },
      { name: "read_run_log", description: "Read retained Trace events for an explicit Run ID, paged by event sequence. Optionally view an evidence_id screenshot referenced by this Run's log. Missing or cleaned records are unavailable.",
        parameters: Type.Object({ run_id: Type.Integer({ minimum: 1 }), start_sequence: Type.Optional(Type.Integer({ minimum: 1 })),
          limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200 })), evidence_id: Type.Optional(Type.String()) }) },
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
      { name: "game_screenshot", description: "Return a fresh original game screenshot and a separate 40px coordinate grid image. Overlays are viewing aids only, never template or evidence pixels. Restores and focuses the unique game window.",
        parameters: Type.Object({}) },
      { name: "preview_crop", description: "Capture the game anew; preview a crop without adding an active Asset. Return full image with crop boundary lines, the clean crop, and same-image template matching at threshold. A match is diagnostic, not proof of cross-state reliability. Returns preview_id for crop_asset to save the identical pixels and parameters.",
        parameters: Type.Object({ logical_name: logicalName,
          region: Type.Object({ x: Type.Integer(), y: Type.Integer(), width: Type.Integer(), height: Type.Integer() }),
          threshold: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
          tags: Type.Optional(Type.Array(Type.String())) }) },
      { name: "crop_asset", description: "Save an existing preview from this conversation using preview_id. Does not recapture. Reuses existing logical-name/hash images and original tags. Preview first with preview_crop.",
        parameters: Type.Object({ preview_id: Type.String() }) },
      { name: "remove_asset", description: "Archive the exact active logical-name/SHA Asset, original tags, reason, and a NEW clean game screenshot. Remove its active image and local tag mapping only after archival preparation. Other logical names are unchanged. No permanent deletion or arbitrary paths. Screenshot failure prevents removal.",
        parameters: Type.Object({ logical_name: logicalName, sha: Type.String({ pattern: "^[0-9a-f]{64}$" }), reason: Type.String({ minLength: 1 }) }) },
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
