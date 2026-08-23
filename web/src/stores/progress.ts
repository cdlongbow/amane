import { create } from "zustand";

/** 单个任务的进度快照, 来自 WS `task.progress` 事件 ({task_id,current,total,message}). */
export interface TaskProgress {
  current: number;
  total: number;
  message: string;
}

interface ProgressState {
  /** 按 task_id 索引的进度. 任务完成/失败时移除. */
  byTask: Record<number, TaskProgress>;
  setProgress: (taskId: number, progress: TaskProgress) => void;
  clearProgress: (taskId: number) => void;
}

/**
 * 任务进度 client 态 -- 高频 `task.progress` 事件写这里, 而非 invalidate REST query
 * (符合 frontend.md 状态边界: 客户端流走 Zustand, 不污染 TanStack Query 缓存).
 */
export const useProgressStore = create<ProgressState>((set) => ({
  byTask: {},
  setProgress: (taskId, progress) => set((s) => ({ byTask: { ...s.byTask, [taskId]: progress } })),
  clearProgress: (taskId) =>
    set((s) => {
      if (!(taskId in s.byTask)) return s;
      const next = { ...s.byTask };
      delete next[taskId];
      return { byTask: next };
    }),
}));
