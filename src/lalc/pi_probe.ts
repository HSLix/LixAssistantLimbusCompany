import { access, readFile, realpath, writeFile } from "node:fs/promises";
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
  const repairTarget = process.env.LALC_PI_REPAIR_TARGET;
  const preflight = process.env.LALC_PI_PREFLIGHT === "1";
  const repairTools = ["read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
                       "action_contracts", "game_screenshot", "crop_asset"];
  const limit = Number(process.env.LALC_PI_MAX_REQUESTS);
  let requests = Number(process.env.LALC_PI_REQUESTS_USED || 0);
  const api = openAICompletionsApi();
  const emit = (type, fields) => console.log(JSON.stringify({ type, ...fields }));
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
      maxTokens: 4096,
    }],
    streamSimple(model, context, options) {
      return api.streamSimple(model, context, {
        ...options,
        maxRetries: 0,
        async onPayload(payload, model) {
          // 扩展事件中的异常会被 pi 捕获；上限必须在客户端回调里拒绝发送。
          if (requests >= limit) throw new Error("LALC request limit reached");
          requests++;
          const shown = JSON.parse(JSON.stringify(payload, (_key, value) =>
            typeof value === "string" && value.startsWith("data:image/")
              ? `[image data URL: ${value.length} characters]` : value));
          if (process.env.LALC_PI_PAYLOAD_DIR) {
            // 大图请求不能与 RPC 事件并发倾倒到 stdout；独立保存完整载荷后只发送引用。
            const payloadPath = join(process.env.LALC_PI_PAYLOAD_DIR!, `request-${requests}.json`);
            const key = process.env.LALC_PI_API_KEY!;
            await writeFile(payloadPath, JSON.stringify(payload, (_name, value) =>
              typeof value === "string" && key !== "lalc-no-key" ? value.replaceAll(key, "[REDACTED]") : value));
            emit("lalc_request", { requests, payload_path: payloadPath });
          } else {
            emit("lalc_request", { requests, payload: shown });
          }
          return options?.onPayload ? await options.onPayload(payload, model) : payload;
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
  if (repairTarget) {
    const checkedEdit = async (path: string) => {
      const target = await checkedPath(root, path);
      if (target !== repairTarget) throw new Error("Only the selected Component may be edited");
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
        const value = await ctx.ui.input("lalc.validate");
        if (value === undefined) throw new Error("Validation cancelled");
        return { content: [{ type: "text", text: value }], details: JSON.parse(value) };
      },
    });
    const logicalName = Type.String({ description: "Complete Asset logical name, e.g. ui/claim" });
    const tools = [
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
          const path = await ctx.ui.input("lalc.tool:" + JSON.stringify({ name: tool.name, arguments: params }));
          if (path === undefined) throw new Error("Repair tool cancelled");
          return JSON.parse(await readFile(path, "utf8"));
        },
      });
    }
  }
  pi.on("session_start", () => {
    pi.setActiveTools(preflight ? [] : repairTarget ? repairTools : ["read"]);
    emit("lalc_ready", { tools: pi.getActiveTools(), root, repairTarget,
                         availableTools: pi.getAllTools().map(tool => tool.name) });
  });
}
