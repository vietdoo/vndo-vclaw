"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  PlatformMetrics,
  AgentInfo,
  ToolCall,
  EventEntry,
  TimeSeriesPoint,
  AgentLoadPoint,
} from "../types";
import {
  generateMetrics,
  generateAgents,
  generateToolCall,
  generateEvent,
  generateTimeSeries,
  generateAgentLoad,
} from "../mock-data";

const METRICS_INTERVAL = 2000;
const FEED_INTERVAL = 1500;
const CHART_INTERVAL = 2000;

export function useMetrics() {
  const [metrics, setMetrics] = useState<PlatformMetrics>(() => generateMetrics());

  useEffect(() => {
    const id = setInterval(() => {
      setMetrics((prev) => generateMetrics(prev));
    }, METRICS_INTERVAL);
    return () => clearInterval(id);
  }, []);

  return metrics;
}

export function useAgents() {
  const [agents, setAgents] = useState<AgentInfo[]>(() => generateAgents());

  useEffect(() => {
    const id = setInterval(() => {
      setAgents(generateAgents());
    }, 3000);
    return () => clearInterval(id);
  }, []);

  return agents;
}

export function useToolCallFeed(maxItems = 20) {
  const [calls, setCalls] = useState<ToolCall[]>(() =>
    Array.from({ length: 8 }, () => generateToolCall())
  );

  useEffect(() => {
    const id = setInterval(() => {
      setCalls((prev) => {
        const next = [generateToolCall(), ...prev];
        return next.slice(0, maxItems);
      });
    }, FEED_INTERVAL);
    return () => clearInterval(id);
  }, [maxItems]);

  return calls;
}

export function useEventFeed(maxItems = 30) {
  const [events, setEvents] = useState<EventEntry[]>(() =>
    Array.from({ length: 10 }, () => generateEvent())
  );

  useEffect(() => {
    const id = setInterval(() => {
      setEvents((prev) => {
        const next = [generateEvent(), ...prev];
        return next.slice(0, maxItems);
      });
    }, 1200);
    return () => clearInterval(id);
  }, [maxItems]);

  return events;
}

export function useTimeSeries(points = 30) {
  const [data, setData] = useState<TimeSeriesPoint[]>(() => generateTimeSeries(points));

  useEffect(() => {
    const id = setInterval(() => {
      setData((prev) => {
        const now = new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        const newPoint: TimeSeriesPoint = {
          time: now,
          requests: Math.floor(Math.random() * 60) + 20,
          latency: Math.floor(Math.random() * 400) + 100,
          errors: Math.floor(Math.random() * 3),
        };
        return [...prev.slice(1), newPoint];
      });
    }, CHART_INTERVAL);
    return () => clearInterval(id);
  }, [points]);

  return data;
}

export function useAgentLoad(points = 30) {
  const [data, setData] = useState<AgentLoadPoint[]>(() => generateAgentLoad(points));

  useEffect(() => {
    const id = setInterval(() => {
      setData((prev) => {
        const now = new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        const newPoint: AgentLoadPoint = {
          time: now,
          task_management: Math.floor(Math.random() * 5),
          public_service: Math.floor(Math.random() * 5),
          document_processor: Math.floor(Math.random() * 3),
          notification_hub: Math.floor(Math.random() * 10),
        };
        return [...prev.slice(1), newPoint];
      });
    }, CHART_INTERVAL);
    return () => clearInterval(id);
  }, [points]);

  return data;
}
