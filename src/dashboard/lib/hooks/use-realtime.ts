"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  PlatformMetrics,
  AgentInfo,
  ToolCall,
  EventEntry,
  LogEntry,
  WorkflowEvent,
  SystemHealth,
  TimeSeriesPoint,
  AgentLoadPoint,
} from "../types";
import {
  generateMetrics,
  generateAgents,
  generateToolCall,
  generateEvent,
  generateLogEntry,
  generateWorkflowEvent,
  generateSystemHealth,
  generateTimeSeries,
  generateAgentLoad,
} from "../mock-data";

export function useMetrics() {
  const [metrics, setMetrics] = useState<PlatformMetrics>(() => generateMetrics());

  useEffect(() => {
    const id = setInterval(() => {
      setMetrics((prev) => generateMetrics(prev));
    }, 2000);
    return () => clearInterval(id);
  }, []);

  return metrics;
}

export function useAgents() {
  const [agents, setAgents] = useState<AgentInfo[]>(() => generateAgents());

  useEffect(() => {
    const id = setInterval(() => setAgents(generateAgents()), 3000);
    return () => clearInterval(id);
  }, []);

  return agents;
}

export function useToolCallFeed(maxItems = 50) {
  const [calls, setCalls] = useState<ToolCall[]>(() =>
    Array.from({ length: 12 }, () => generateToolCall())
  );

  useEffect(() => {
    const id = setInterval(() => {
      setCalls((prev) => [generateToolCall(), ...prev].slice(0, maxItems));
    }, 1200);
    return () => clearInterval(id);
  }, [maxItems]);

  return calls;
}

export function useEventFeed(maxItems = 60) {
  const [events, setEvents] = useState<EventEntry[]>(() =>
    Array.from({ length: 15 }, () => generateEvent())
  );

  useEffect(() => {
    const id = setInterval(() => {
      setEvents((prev) => [generateEvent(), ...prev].slice(0, maxItems));
    }, 900);
    return () => clearInterval(id);
  }, [maxItems]);

  return events;
}

export function useLogFeed(maxItems = 100) {
  const [logs, setLogs] = useState<LogEntry[]>(() =>
    Array.from({ length: 20 }, () => generateLogEntry())
  );

  useEffect(() => {
    const id = setInterval(() => {
      setLogs((prev) => [generateLogEntry(), ...prev].slice(0, maxItems));
    }, 800);
    return () => clearInterval(id);
  }, [maxItems]);

  return logs;
}

export function useWorkflowFeed(maxItems = 50) {
  const [workflows, setWorkflows] = useState<WorkflowEvent[]>(() =>
    Array.from({ length: 15 }, () => generateWorkflowEvent())
  );

  useEffect(() => {
    const id = setInterval(() => {
      setWorkflows((prev) => [generateWorkflowEvent(), ...prev].slice(0, maxItems));
    }, 1500);
    return () => clearInterval(id);
  }, [maxItems]);

  return workflows;
}

export function useSystemHealth() {
  const [health, setHealth] = useState<SystemHealth>(() => generateSystemHealth());

  useEffect(() => {
    const id = setInterval(() => setHealth(generateSystemHealth()), 2000);
    return () => clearInterval(id);
  }, []);

  return health;
}

export function useTimeSeries(points = 40) {
  const [data, setData] = useState<TimeSeriesPoint[]>(() => generateTimeSeries(points));

  useEffect(() => {
    const id = setInterval(() => {
      setData((prev) => {
        const time = new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        const requests = Math.floor(Math.random() * 60) + 20;
        return [
          ...prev.slice(1),
          {
            time,
            requests,
            latency: Math.floor(Math.random() * 400) + 100,
            errors: Math.floor(Math.random() * Math.ceil(requests * 0.05)),
            p95: Math.floor(Math.random() * 400) + 300,
          },
        ];
      });
    }, 2000);
    return () => clearInterval(id);
  }, [points]);

  return data;
}

export function useAgentLoad(points = 40) {
  const [data, setData] = useState<AgentLoadPoint[]>(() => generateAgentLoad(points));

  useEffect(() => {
    const id = setInterval(() => {
      setData((prev) => {
        const time = new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        return [
          ...prev.slice(1),
          {
            time,
            task_management: Math.floor(Math.random() * 5),
            public_service: Math.floor(Math.random() * 5),
            document_processor: Math.floor(Math.random() * 3),
            notification_hub: Math.floor(Math.random() * 10),
          },
        ];
      });
    }, 2000);
    return () => clearInterval(id);
  }, [points]);

  return data;
}
