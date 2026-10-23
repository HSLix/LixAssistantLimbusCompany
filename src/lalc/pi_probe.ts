import { access, readFile, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import { createReadTool } from "@earendil-works/pi-coding-agent";
import { openAICompletionsApi } from "@earendil-works/pi-ai";

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
          emit("lalc_request", { requests, payload: shown });
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
  pi.on("session_start", () => {
    pi.setActiveTools(["read"]);
    emit("lalc_ready", { tools: pi.getActiveTools(), root });
  });
}
