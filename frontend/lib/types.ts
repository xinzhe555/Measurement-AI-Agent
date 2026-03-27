// lib/types.ts
// 與 backend/schemas/response.py 完全對應

export interface PigeResult {
  xoc_um: number
  yoc_um: number
  zoc_um: number
  aoc_deg: number
  boc_deg: number
  xoa_um: number
  yoa_um: number
  zoa_um: number
  boa_deg: number
  coa_deg: number
  xoc_error_pct?: number
  aoc_error_pct?: number
  boa_error_pct?: number
}

export interface PdgeResult {
  exc_amp_um: number
  exc_phase_deg: number
  eyc_amp_um: number
  eyc_phase_deg: number
  ezc_amp_um: number
  ezc_freq: number
  eac_deg: number
  ebc_deg: number
}

export interface RmsComparison {
  before_dx_um: number
  before_dy_um: number
  before_dz_um: number
  after_phys_dx_um: number
  after_phys_dy_um: number
  after_phys_dz_um: number
  after_ai_dx_um?: number
  after_ai_dy_um?: number
  after_ai_dz_um?: number
  phys_improvement_dx_pct: number
  phys_improvement_dy_pct: number
  phys_improvement_dz_pct: number
}

export interface DiagnosticFinding {
  severity: 'critical' | 'warning' | 'info'
  parameter: string
  value_str: string
  message: string
  instrument: string
}

export interface AnalyzeResponse {
  success: boolean
  session_id: string
  pige: PigeResult
  pdge: PdgeResult
  rms: RmsComparison
  findings: DiagnosticFinding[]
  ai_r2?: number
  error_message?: string
}

export interface AnalyzeRequest {
  mode: 'simulate' | 'upload'
  path_type?: string
  view_mode?: string
  ball_x?: number
  ball_y?: number
  ball_z?: number
  tool_length?: number  
  
  inject_xoc?: number
  inject_yoc?: number
  inject_aoc?: number
  inject_boa?: number
  inject_exc?: number
  inject_eyc?: number
  inject_ezc?: number
  run_ai_layer?: boolean
  dx?: number[]
  dy?: number[]
  dz?: number[]
  a_cmd?: number[]
  c_cmd?: number[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'system'
  content: string
  timestamp: string
  analysisResult?: AnalyzeResponse
  usedTools?: string[]
  chartData?: any[];
}

export interface TwinChartPoint {
  index: number
  a_axis: number   // A 軸角度 (deg)
  c_axis: number   // C 軸角度 (deg)
  dx: number       // 誤差 X (μm)
  dy: number       // 誤差 Y (μm)
  dz: number       // 誤差 Z (μm)
}

export interface ChatRequest {
  message: string
  session_id: string
  // context 帶入最新分析結果，讓 Agent 能引用具體數值
  context?: {
    last_analysis?: AnalyzeResponse | null
    twin_chart_data?: TwinChartPoint[]   // TwinPanel 匯出的圖表原始數據
  } | null
}
