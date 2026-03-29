"use client";

/**
 * 全局智能日历请求 store（React Context）。
 *
 * 请求在 Provider 层发起，切换页面不会中断；回到 smart-calendar 页时
 * 可直接读取 loading / data / error 状态。
 */

import axios from "axios";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

const API_BASE = "";

/* ── 类型 ── */

export type FilteredEvent = {
  event_uid: string;
  title: string;
  start_iso: string;
  end_iso: string;
  all_day: boolean;
  source: string;
  location: string;
  url: string;
  description: string;
  categories: string[];
  relevance_score: number;
  reason: string;
};

export type FilterResult = {
  summary: string;
  filtered_events: FilteredEvent[];
};

export type SmartCalendarApiResponse = {
  result: FilterResult;
  agent_steps: number;
  model: string;
  thread_id: string;
};

export interface SmartPlanParams {
  goals: string;
  focus_areas: string[];
  horizon_days: number;
  grade: string;
  timetable_busy: Record<string, string[][]> | null;
  thread_id?: string;
  followup?: string;
}

type StoreValue = {
  loading: boolean;
  followupLoading: boolean;
  data: SmartCalendarApiResponse | null;
  error: string | null;
  threadId: string | null;
  submit: (params: SmartPlanParams) => void;
  followup: (params: SmartPlanParams) => void;
  clear: () => void;
};

const Ctx = createContext<StoreValue | null>(null);

/* ── Provider ── */

export function SmartCalendarProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [loading, setLoading] = useState(false);
  const [followupLoading, setFollowupLoading] = useState(false);
  const [data, setData] = useState<SmartCalendarApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);

  const inflightRef = useRef(0);

  const submit = useCallback((params: SmartPlanParams) => {
    const id = ++inflightRef.current;
    setError(null);
    setData(null);
    setThreadId(null);
    setLoading(true);
    axios
      .post<SmartCalendarApiResponse>(
        `${API_BASE}/api/calendar/smart-plan`,
        params,
        { withCredentials: true, timeout: 180_000 },
      )
      .then((res) => {
        if (inflightRef.current !== id) return;
        setData(res.data);
        setThreadId(res.data.thread_id || null);
      })
      .catch((ex) => {
        if (inflightRef.current !== id) return;
        if (axios.isAxiosError(ex)) {
          const d = ex.response?.data;
          setError(
            typeof d?.detail === "string"
              ? d.detail
              : "生成失败，请确认已登录且后端已配置 DEEPSEEK_API_KEY",
          );
        } else {
          setError("网络错误，请确认后端服务正在运行");
        }
      })
      .finally(() => {
        if (inflightRef.current !== id) return;
        setLoading(false);
      });
  }, []);

  const followup = useCallback((params: SmartPlanParams) => {
    const id = ++inflightRef.current;
    setError(null);
    setFollowupLoading(true);
    axios
      .post<SmartCalendarApiResponse>(
        `${API_BASE}/api/calendar/smart-plan`,
        params,
        { withCredentials: true, timeout: 180_000 },
      )
      .then((res) => {
        if (inflightRef.current !== id) return;
        setData(res.data);
        setThreadId(res.data.thread_id || null);
      })
      .catch((ex) => {
        if (inflightRef.current !== id) return;
        if (axios.isAxiosError(ex)) {
          const d = ex.response?.data;
          setError(
            typeof d?.detail === "string" ? d.detail : "追问失败，请稍后重试",
          );
        } else {
          setError("网络错误");
        }
      })
      .finally(() => {
        if (inflightRef.current !== id) return;
        setFollowupLoading(false);
      });
  }, []);

  const clear = useCallback(() => {
    inflightRef.current++;
    setLoading(false);
    setFollowupLoading(false);
    setData(null);
    setError(null);
    setThreadId(null);
  }, []);

  const value = useMemo(
    () => ({ loading, followupLoading, data, error, threadId, submit, followup, clear }),
    [loading, followupLoading, data, error, threadId, submit, followup, clear],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSmartCalendarStore() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSmartCalendarStore 必须在 SmartCalendarProvider 内使用");
  return ctx;
}
