export interface ScoreDetail {
  trend:             number;   // /30
  momentum:          number;   // /25
  risk_reward:       number;   // /20
  relative_strength: number;   // /15
  volume_quality:    number;   // /10
  details: {
    prix_above_sma200:    boolean;
    sma50_above_sma200:   boolean;
    sma50_slope_positive: boolean;
    near_52w_high:        boolean;
    rsi_ideal_zone:       boolean;
    macd_positif:         boolean;
    perf_3m_positive:     boolean;
    outperforms_sp500:    boolean;
    volume_eleve:         boolean;
    rr_suffisant:         boolean;
  };
}

export interface TickerResult {
  ticker:        string;
  sector:        string;
  price:         number;
  score:         number;
  // Grades
  setup_grade:   "A+" | "A" | "B" | "REJECT";
  setup_reason:  string;
  confidence:    number;   // 0–100
  quality_score: number;   // 0–100 — timing quality
  // Rétrocompat
  category:      "BUY NOW" | "WAIT / SMALL POSITION" | "WAIT PULLBACK" | "WATCHLIST" | "AVOID";
  position_size: string;
  signal_type:   "Momentum" | "Pullback" | "Breakout" | "Neutral";
  // Niveaux dynamiques
  entry:         number;
  stop_loss:     number;
  sl_type:       "ATR" | "Structure" | "Support";
  tp1:           number;
  tp2:           number;
  take_profit:   number;
  trailing_stop: number;
  resistance:    number;
  support:       number;
  high_52w:      number;
  rr_ratio:      number;
  // Métriques
  risk_now_pct:   number;
  dist_entry_pct: number;
  trend_status:   string;
  sma50:          number;
  sma200:         number;
  rsi_val:        number;
  macd_val:       number;
  atr_val:        number;
  perf_3m:        number;
  perf_6m:        number;
  score_detail:   ScoreDetail;
  // Earnings
  earnings_date?:    string | null;
  earnings_days?:    number | null;
  earnings_warning?: boolean;
  // Setup status (indépendant du marché ouvert/fermé)
  setup_status?:     "READY" | "WAIT" | "INVALID";
  // Filtres fondamentaux
  risk_filters_status?: "OK" | "CAUTION" | "BLOCKED";
  risk_filter_reasons?: string[];
  fundamental_risk?:    "LOW" | "MEDIUM" | "HIGH";
  news_risk?:           "LOW" | "MEDIUM" | "HIGH";
  sector_rank?:         "STRONG" | "NEUTRAL" | "WEAK";
  vix_risk?:            "LOW" | "MEDIUM" | "HIGH";
  final_decision?:      "BUY" | "WAIT" | "SKIP";
  error?:            string;
}

// ── Setup Stats (validation historique) ──────────────────────────────────────

export interface SetupStats {
  n_trades:          number;
  win_rate?:         number;
  expectancy?:       number;
  profit_factor?:    number;
  max_drawdown_pct?: number;
  avg_duration_days?:number;
  avg_gain_pct?:     number;
  avg_loss_pct?:     number;
  sample_ok?:        boolean;
  grade?:            string;
  period_months?:    number;
  warning?:          string;
  error?:            string;
}

// ── Market Context ────────────────────────────────────────────────────────────

export interface SectorStrength {
  perf_1m: number;
  perf_3m: number;
  rsi:     number;
  etf:     string;
}

export interface MarketContext {
  vix:                number;
  vix_regime:         "LOW" | "NORMAL" | "ELEVATED" | "HIGH" | "EXTREME";
  market_breadth_pct: number;
  sector_strength:    Record<string, SectorStrength>;
  condition:          "FAVORABLE" | "NEUTRAL" | "DANGEROUS";
  condition_label:    string;
  condition_emoji:    string;
  condition_score:    number;
  positive_sectors:   number;
  total_sectors:      number;
}

// ── Signal Tracking ───────────────────────────────────────────────────────────

export interface TrackedSignal {
  id:          number;
  ticker:      string;
  date:        string;
  price:       number;
  entry:       number;
  stop_loss:   number;
  tp1:         number;
  tp2:         number;
  setup_grade: string;
  score:       number;
  confidence:  number;
  rr_ratio:    number;
  signal_type: string;
  strategy:    string;
  outcome:        "TP1" | "TP2" | "SL" | "OPEN" | null;
  pnl_pct:        number | null;
  days_held:      number | null;
  updated_at:     string | null;
  outcome_source: "ohlc" | "snapshot" | "pending" | null;
}

export interface SignalGradeStats {
  total:    number;
  closed:   number;
  wins:     number;
  win_rate: number;
  avg_pnl:  number;
}

export interface SignalTrackerData {
  signals: TrackedSignal[];
  stats: {
    total:         number;
    closed:        number;
    open:          number;
    wins:          number;
    losses:        number;
    win_rate:      number;
    avg_pnl:       number;
    ohlc_win_rate: number | null;
    ohlc_closed:   number;
    by_grade:      Record<string, SignalGradeStats>;
  };
}

export interface BacktestTrade {
  entry_date:    string;
  exit_date:     string;
  entry_price:   number;
  exit_price:    number;
  exit_reason:   "TP" | "SL" | "TIMEOUT" | "OPEN";
  pnl_pct:       number;
  duration_days: number;
}

export interface BacktestResult {
  ticker:           string;
  total_trades:     number;
  wins:             number;
  losses:           number;
  win_rate:         number;
  avg_gain_pct:     number;
  avg_loss_pct:     number;
  expectancy:       number;
  max_drawdown_pct: number;
  best_trade_pct:   number;
  worst_trade_pct:  number;
  total_return_pct: number;
  avg_duration_days:number;
  reliable:         boolean;
  trades:           BacktestTrade[];
  error?:           string;
}

// Metrics renvoyées par run_portfolio_backtest — partagées par Backtest + Strategy Lab
export interface PortfolioMetrics {
  total_trades:             number;
  wins:                     number;
  losses:                   number;
  win_rate:                 number;
  expectancy:               number;
  profit_factor:            number;
  max_drawdown_pct:         number;
  sharpe_ratio:             number;
  cagr_pct:                 number;
  final_capital:            number;
  total_return_pct:         number;
  time_in_market_pct:       number;
  max_concurrent_positions: number;
  avg_duration_days:        number;
  tradable_status:          "TRADABLE" | "À CONFIRMER" | "NON TRADABLE";
  tradable_color:            string;
  tradable_emoji:            string;
  equity_curve:             number[];
}

export interface BacktestSummary {
  results:               BacktestResult[];
  global_win_rate:       number;
  global_expectancy:     number;
  global_total_trades:   number;
  global_reliable_count: number;
  best_ticker:           string;
  worst_ticker:          string;
  portfolio?:            PortfolioMetrics | null;
}

// ── Social Sentiment ─────────────────────────────────────────────────────────

export interface SentimentResult {
  ticker:                string;
  twitter_score:         number;
  reddit_score:          number;
  sentiment_score:       number;
  sentiment_label:       "Very Bullish" | "Bullish" | "Neutral" | "Bearish" | "Very Bearish";
  hype_risk:             "Low" | "Medium" | "High";
  mention_volume:        number;
  sentiment_trend:       "Improving" | "Stable" | "Declining";
  divergence:            boolean;
  summary:               string;
  impact_on_trade_signal:string;
  twitter_error?:        string | null;
  reddit_error?:         string | null;
  cached:                boolean;
  vader_available:       boolean;
}

// ── Strategy Lab ──────────────────────────────────────────────────────────────

export interface WalkForward {
  train_trades:     number;
  train_win_rate:   number;
  train_pf:         number;
  train_expectancy: number;
  test_trades:      number;
  test_win_rate:    number;
  test_pf:          number;
  test_expectancy:  number;
  wr_degradation:   number;
  pf_degradation:   number;
}

export interface LabStrategyResult {
  key:               string;
  name:              string;
  description:       string;
  color:             string;
  emoji:             string;
  tp_pct:            number;
  sl_pct:            number;
  screener_strategy: "standard" | "conservative";
  screener_signal:   string;
  period_months:     number;
  // Trade stats
  total_trades:      number;
  wins:              number;
  losses:            number;
  win_rate:          number;
  expectancy:        number;
  expectancy_dollars?: number;
  profit_factor:     number;
  max_drawdown_pct:  number;
  total_return_pct:  number;
  avg_duration_days: number;
  reliable_tickers:  number;
  best_ticker:       string;
  worst_ticker:      string;
  score:             number;
  eligible:          boolean;
  // Portfolio metrics
  sharpe_ratio:             number;
  cagr_pct:                 number;
  final_capital:            number;
  time_in_market_pct:       number;
  max_concurrent_positions: number;
  tradable_status:          "TRADABLE" | "À CONFIRMER" | "NON TRADABLE";
  tradable_color:            string;
  tradable_emoji:            string;
  // Curves & details
  equity_curve:      number[];
  ticker_returns:    Record<string, number>;
  // Walk-forward & overfitting (v2)
  walk_forward?:        WalkForward;
  overfitting_risk?:    boolean;
  overfitting_reasons?: string[];
}

export interface LabSummary {
  strategies:          LabStrategyResult[];
  best_overall:        string;
  best_win_rate:       string;
  best_expectancy:     string;
  best_pf?:            string;
  best_low_dd?:        string;
  has_robust_strategy?: boolean;
  tradable_count?:     number;
  confirmed_count?:    number;
  period_months:       number;
}

// ── Parameter Optimizer ───────────────────────────────────────────────────────

export interface OptimizedParamSet {
  rank:             number;
  family:           string;
  score:            number;
  win_rate:         number;
  expectancy:       number;
  profit_factor:    number;
  max_drawdown_pct: number;
  total_trades:     number;
  total_return_pct: number;
  eligible:         boolean;
  params: {
    dist_min:     number;
    dist_max:     number;
    rsi_min:      number;
    rsi_max:      number;
    req_uptrend:  boolean;
    req_macd:     boolean;
    req_vol:      boolean;
    vol_mult:     number;
    req_new_high: boolean;
    perf_3m_min:  number;
    tp_pct:       number;
    sl_pct:       number;
    max_days:     number;
  };
}

export interface OptimizerResult {
  top:             OptimizedParamSet[];
  total_tested:    number;
  eligible_count:  number;
  has_eligible:    boolean;
  tickers_used:    number;
  period_months:   number;
  from_cache:      boolean;
  stats: {
    avg_score:      number;
    avg_win_rate:   number;
    avg_expectancy: number;
  };
}

// ── Market Regime ─────────────────────────────────────────────────────────────

export interface MarketRegime {
  regime:        "BULL" | "BEAR" | "RANGE" | "UNKNOWN";
  spy_price:     number;
  spy_sma50:     number;
  spy_sma200:    number;
  spy_rsi:       number;
  spy_perf_1m:   number;
  data_ok?:      boolean;
  data_warning?: string | null;
}
