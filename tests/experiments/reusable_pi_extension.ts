// 验证专用：每轮配置通过固定命令重置，不改变生产扩展。
import { readFile, realpath } from "node:fs/promises";
import { writeSync } from "node:fs";
import { createReadTool } from "@earendil-works/pi-coding-agent";
import { openAICompletionsApi, Type } from "@earendil-works/pi-ai";

export default function (pi) {
  let round: any;
  let requests = 0;
  const emit = (type, fields = {}) => writeSync(1, JSON.stringify({ type, pid: process.pid, ...fields }) + "\n");
  const api = openAICompletionsApi();
  pi.registerProvider("validation", {
    baseUrl: process.env.LALC_PI_BASE_URL,
    apiKey: "$LALC_PI_API_KEY",
    api: "openai-completions",
    models: ["model-a", "model-b"].map(id => ({ id, name: id, reasoning: false,
      input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 65536, maxTokens: 1024 })),
    streamSimple(model, context, options) {
      if (++requests > round.limit) throw new Error("validation round request limit");
      emit("validation_request", { round: round.number, requests });
      return api.streamSimple(model, context, { ...options, maxRetries: 0 });
    },
  });
  pi.registerTool({
    name: "probe_read", label: "Validation read", description: "Read only the active round root.",
    parameters: Type.Object({ path: Type.String() }),
    async execute(id, params, signal, onUpdate) {
      if (!round.tools.includes("probe_read")) throw new Error("not authorized in this round");
      const { checkedPath } = await import("../../src/lalc/pi_probe.ts");
      const path = await checkedPath(round.root, params.path);
      return createReadTool(round.root).execute(id, { ...params, path }, signal, onUpdate);
    },
  });
  pi.registerTool({
    name: "probe_write", label: "Validation write", description: "Authorization sentinel, never writes.",
    parameters: Type.Object({}),
    async execute() {
      if (!round.tools.includes("probe_write")) throw new Error("not authorized in this round");
      return { content: [{ type: "text", text: "authorized; no write performed" }] };
    },
  });
  pi.on("context", event => ({ messages: [...round.history, ...event.messages] }));
  pi.on("before_agent_start", () => ({ systemPrompt: round.system }));
  pi.on("session_start", async (_event, ctx) => {
    emit("validation_ready");
    if (!process.env.LALC_VALIDATION_CONFIG) return;
    round = JSON.parse(await readFile(process.env.LALC_VALIDATION_CONFIG, "utf8"));
    round.root = await realpath(round.root);
    requests = 0;
    pi.setActiveTools(round.tools);
    if (!await pi.setModel(ctx.modelRegistry.find("validation", round.model))) {
      throw new Error("validation model not found");
    }
    emit("validation_round_ready", { round: round.number, tools: pi.getActiveTools(), requests });
  });
  pi.registerCommand("validation_begin", {
    description: "Load isolated validation round state without model inference.",
    async handler(path, ctx) {
      await ctx.waitForIdle();
      process.env.LALC_VALIDATION_CONFIG = path;
      await ctx.newSession();
    },
  });
  pi.registerCommand("validation_crash", {
    description: "Validation only: exit immediately to probe in-flight transport failure.",
    async handler() { process.exit(7); },
  });
}
