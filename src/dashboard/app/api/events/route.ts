
export const runtime = "edge";
export const dynamic = "force-dynamic";

// ---- types ---------------------------------------------------------------
export type EventKind =
  | "workflow.started"
  | "workflow.completed"
  | "workflow.failed"
  | "agent.dispatched"
  | "agent.completed"
  | "agent.failed"
  | "tool.called"
  | "tool.returned"
  | "metrics.snapshot";

export interface DashboardEvent {
  id: string;
  kind: EventKind;
  ts: number;
  payload: Record<string, unknown>;
}

// ---- data pools ---------------------------------------------------------
const AGENTS = [
  "task_management",
  "public_service",
  "search_agent",
  "summarizer",
  "code_reviewer",
];

const TOOLS = [
  "create_task",
  "move_task",
  "list_tasks",
  "lookup_service",
  "submit_app",
  "check_status",
  "web_search",
  "summarize_text",
  "run_lint",
  "format_code",
];

const INTENTS = [
  "create_project_task",
  "lookup_public_record",
  "search_knowledge_base",
  "summarize_document",
  "review_code_diff",
];

function ulid(): string {
  return Math.random().toString(36).slice(2, 10).toUpperCase() +
    Date.now().toString(36).toUpperCase();
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randFloat(min: number, max: number, decimals = 1): number {
  return parseFloat((Math.random() * (max - min) + min).toFixed(decimals));
}

// ---- state accumulators -------------------------------------------------
let totalWorkflows = 142;
let completedWorkflows = 138;
let failedWorkflows = 4;
let totalAgentCalls = 891;
let avgLatencyMs = 312;
let p99LatencyMs = 1480;
let activeTasks = 0;
let uptimeSeconds = 3600 * 4;

// ---- event generators ---------------------------------------------------
function genEvent(): DashboardEvent {
  const roll = Math.random();
  uptimeSeconds += 1;

  if (roll < 0.12) {
    // metrics snapshot every ~8 events
    totalWorkflows += randInt(0, 2);
    completedWorkflows += randInt(0, 2);
    if (Math.random() < 0.04) failedWorkflows++;
    avgLatencyMs = Math.max(80, avgLatencyMs + randInt(-20, 25));
    p99LatencyMs = Math.max(200, p99LatencyMs + randInt(-50, 70));
    const successRate = totalWorkflows > 0
      ? parseFloat(((completedWorkflows / totalWorkflows) * 100).toFixed(1))
      : 100;
    return {
      id: ulid(),
      kind: "metrics.snapshot",
      ts: Date.now(),
      payload: {
        totalWorkflows,
        completedWorkflows,
        failedWorkflows,
        totalAgentCalls,
        avgLatencyMs,
        p99LatencyMs,
        activeTasks,
        successRate,
        uptimeSeconds,
        activeAgents: AGENTS.length,
      },
    };
  }

  if (roll < 0.28) {
    // workflow started
    activeTasks++;
    totalWorkflows++;
    const wfId = ulid();
    return {
      id: ulid(),
      kind: "workflow.started",
      ts: Date.now(),
      payload: {
        workflowId: wfId,
        intent: pick(INTENTS),
        source: pick(["telegram", "api"]),
        tenantId: `t_${randInt(1, 5)}`,
      },
    };
  }

  if (roll < 0.48) {
    // agent dispatched
    totalAgentCalls++;
    return {
      id: ulid(),
      kind: "agent.dispatched",
      ts: Date.now(),
      payload: {
        workflowId: ulid(),
        agentName: pick(AGENTS),
        subtaskId: ulid(),
        attempt: randInt(0, 1),
      },
    };
  }

  if (roll < 0.66) {
    // agent completed
    activeTasks = Math.max(0, activeTasks - 1);
    completedWorkflows++;
    const latency = randFloat(55, 950);
    return {
      id: ulid(),
      kind: "agent.completed",
      ts: Date.now(),
      payload: {
        workflowId: ulid(),
        agentName: pick(AGENTS),
        subtaskId: ulid(),
        durationMs: latency,
        tokenUsage: { prompt: randInt(200, 2000), completion: randInt(50, 500) },
      },
    };
  }

  if (roll < 0.72) {
    // agent failed
    failedWorkflows++;
    return {
      id: ulid(),
      kind: "agent.failed",
      ts: Date.now(),
      payload: {
        workflowId: ulid(),
        agentName: pick(AGENTS),
        subtaskId: ulid(),
        error: pick([
          "LLM rate limit exceeded",
          "Agent timeout after 60s",
          "Tool call parameter error",
          "Dependency resolution failed",
        ]),
      },
    };
  }

  if (roll < 0.84) {
    // tool called
    return {
      id: ulid(),
      kind: "tool.called",
      ts: Date.now(),
      payload: {
        toolName: pick(TOOLS),
        agentName: pick(AGENTS),
        workflowId: ulid(),
        params: { input: `arg_${randInt(1, 999)}` },
      },
    };
  }

  if (roll < 0.94) {
    // tool returned
    return {
      id: ulid(),
      kind: "tool.returned",
      ts: Date.now(),
      payload: {
        toolName: pick(TOOLS),
        agentName: pick(AGENTS),
        workflowId: ulid(),
        durationMs: randFloat(10, 400),
        success: Math.random() > 0.1,
      },
    };
  }

  // workflow completed or failed
  activeTasks = Math.max(0, activeTasks - 1);
  const failed = Math.random() < 0.06;
  if (failed) failedWorkflows++;
  else completedWorkflows++;

  return {
    id: ulid(),
    kind: failed ? "workflow.failed" : "workflow.completed",
    ts: Date.now(),
    payload: {
      workflowId: ulid(),
      durationMs: randFloat(200, 3000),
      ...(failed ? { error: "Subtask dependency chain broken" } : {}),
    },
  };
}

// ---- SSE handler --------------------------------------------------------
export async function GET() {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      // send initial snapshot immediately
      const snapshot: DashboardEvent = {
        id: ulid(),
        kind: "metrics.snapshot",
        ts: Date.now(),
        payload: {
          totalWorkflows,
          completedWorkflows,
          failedWorkflows,
          totalAgentCalls,
          avgLatencyMs,
          p99LatencyMs,
          activeTasks,
          successRate: parseFloat(((completedWorkflows / totalWorkflows) * 100).toFixed(1)),
          uptimeSeconds,
          activeAgents: AGENTS.length,
        },
      };
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(snapshot)}\n\n`));

      const interval = setInterval(() => {
        try {
          const ev = genEvent();
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
        } catch {
          clearInterval(interval);
          controller.close();
        }
      }, 700);

      // cleanup on close
      return () => clearInterval(interval);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
