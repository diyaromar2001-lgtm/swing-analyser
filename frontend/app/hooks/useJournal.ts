"use client";

import { useState, useCallback } from "react";
import { JournalTrade } from "../types";

const ACTIVE_KEY = "sw_active_trades";
const CLOSED_KEY = "sw_closed_trades";

function load<T>(key: string): T[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(key) ?? "[]"); }
  catch { return []; }
}
function save<T>(key: string, data: T[]) {
  localStorage.setItem(key, JSON.stringify(data));
}

export function useJournal() {
  const [activeTrades, setActiveTrades] = useState<JournalTrade[]>(() => load<JournalTrade>(ACTIVE_KEY));
  const [closedTrades, setClosedTrades] = useState<JournalTrade[]>(() => load<JournalTrade>(CLOSED_KEY));

  const addTrade = useCallback((trade: JournalTrade) => {
    setActiveTrades(prev => {
      const next = [trade, ...prev];
      save(ACTIVE_KEY, next);
      return next;
    });
  }, []);

  const closeTrade = useCallback((id: string, closeData: {
    date_exit: string;
    price_exit: number;
    reason_exit: "TP1" | "TP2" | "SL" | "MANUAL";
    note_exit?: string;
  }) => {
    setActiveTrades(prev => {
      const trade = prev.find(t => t.id === id);
      if (!trade) return prev;

      const durationDays = Math.max(0, Math.round(
        (new Date(closeData.date_exit).getTime() - new Date(trade.date_entry).getTime()) / 86_400_000
      ));
      const pnlUsd = (closeData.price_exit - trade.price_entry) * trade.quantity - trade.fees;
      const pnlPct = ((closeData.price_exit - trade.price_entry) / trade.price_entry) * 100;
      const riskPerShare = trade.price_entry - trade.stop_loss;
      const rMultiple = riskPerShare > 0 ? pnlUsd / (riskPerShare * trade.quantity) : 0;

      const closed: JournalTrade = {
        ...trade,
        ...closeData,
        status:        closeData.reason_exit,
        pnl_usd:       Math.round(pnlUsd * 100) / 100,
        pnl_pct:       Math.round(pnlPct * 100) / 100,
        r_multiple:    Math.round(rMultiple * 100) / 100,
        duration_days: durationDays,
      };

      const nextActive = prev.filter(t => t.id !== id);
      save(ACTIVE_KEY, nextActive);

      setClosedTrades(cp => {
        const nc = [closed, ...cp];
        save(CLOSED_KEY, nc);
        return nc;
      });

      return nextActive;
    });
  }, []);

  const deleteTrade = useCallback((id: string, fromActive: boolean) => {
    if (fromActive) {
      setActiveTrades(prev => {
        const next = prev.filter(t => t.id !== id);
        save(ACTIVE_KEY, next);
        return next;
      });
    } else {
      setClosedTrades(prev => {
        const next = prev.filter(t => t.id !== id);
        save(CLOSED_KEY, next);
        return next;
      });
    }
  }, []);

  const updateTrade = useCallback((id: string, updates: Partial<JournalTrade>) => {
    setActiveTrades(prev => {
      const next = prev.map(t => t.id === id ? { ...t, ...updates } : t);
      save(ACTIVE_KEY, next);
      return next;
    });
  }, []);

  const isTickerActive = useCallback((ticker: string) => {
    return activeTrades.some(t => t.ticker === ticker && t.status === "OPEN");
  }, [activeTrades]);

  return { activeTrades, closedTrades, addTrade, closeTrade, deleteTrade, updateTrade, isTickerActive };
}
