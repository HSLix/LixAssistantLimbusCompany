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
  const limit = Number(process.env.LALC_PI_MAX_REQUESTS);
  let requests = 0;
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
          if (repairTarget) {
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
  }
  pi.on("session_start", () => {
    pi.setActiveTools(repairTarget ? ["read", "edit", "validate"] : ["read"]);
    emit("lalc_ready", { tools: pi.getActiveTools(), root, repairTarget,
                         availableTools: pi.getAllTools().map(tool => tool.name) });
  });
}
