import React, { useState } from 'react';
import {
  Check,
  Code2,
  Copy,
  Download,
  Play,
  Plug,
  Terminal,
  X,
} from 'lucide-react';
import { McpLogEntry } from '../types/snvn';
import {
  BRIDGE_README_MD,
  CSHARP_CSPROJ_CODE,
  CSHARP_OBJECTARX_CODE,
  PYTHON_ACTIVEX_MCP_CODE,
  PYTHON_REQUIREMENTS_TXT,
  downloadAutoCadBridgeZip,
} from '../mcp/bridgeTemplates';

interface McpBridgeModalProps {
  open: boolean;
  onClose: () => void;
  endpoint: string;
  onEndpointChange: (url: string) => void;
  useSandbox: boolean;
  onUseSandboxChange: (val: boolean) => void;
  connectionInfo: string;
  logs: McpLogEntry[];
  onRunTool: (toolName: string) => void;
}

type ModalTab = 'tools' | 'python' | 'csharp' | 'guide';

export const McpBridgeModal: React.FC<McpBridgeModalProps> = ({
  open,
  onClose,
  endpoint,
  onEndpointChange,
  useSandbox,
  onUseSandboxChange,
  connectionInfo,
  logs,
  onRunTool,
}) => {
  const [tab, setTab] = useState<ModalTab>('tools');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  if (!open) return null;

  const copyCode = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1800);
    } catch {
      // ignore clipboard restrictions
    }
  };

  const handleDownloadKit = async () => {
    setDownloading(true);
    try {
      await downloadAutoCadBridgeZip();
    } finally {
      setDownloading(false);
    }
  };

  const mcpTools = [
    {
      name: 'autocad_ping',
      title: 'Kiểm tra kết nối AutoCAD 2022',
      desc: 'Đọc phiên bản AutoCAD 2022, tên tệp DWG đang mở và danh sách Layer.',
    },
    {
      name: 'autocad_read_survey_entities',
      title: 'Đọc dữ liệu trắc địa DWG (6 đối tượng SNVN)',
      desc: 'Trích xuất Point 3D, Block, Single Text, Line, 2D Polyline, 3D Polyline đứt gãy vào MHTN.',
    },
    {
      name: 'autocad_read_boundaries',
      title: 'Đọc biên đào đắp & vùng bỏ qua',
      desc: 'Đọc LWPOLYLINE khép kín từ lớp SNVN_BIEN và SNVN_VUNG_BOQUA.',
    },
    {
      name: 'autocad_draw_grid_results',
      title: 'Vẽ lưới ô vuông & khối lượng sang DWG',
      desc: 'Ghi lưới ô vuông, 4 góc cao độ nút, đường ranh giới 0 và vòng tròn khối lượng SNVN.',
    },
    {
      name: 'autocad_draw_contours_taluy',
      title: 'Vẽ đường đồng mức & Taluy 2D sang DWG',
      desc: 'Ghi LWPOLYLINE đồng mức cái/con kèm cao độ Elevation và vạch dài/ngắn Taluy.',
    },
    {
      name: 'autocad_draw_cross_section',
      title: 'Vẽ mặt cắt ngang chuẩn TCVN sang DWG',
      desc: 'Xuất tuyến mặt cắt đang chọn kèm đường tự nhiên, thiết kế và bảng gióng chân.',
    },
    {
      name: 'autocad_insert_snvn_tables',
      title: 'Chèn bảng thống kê khối lượng (AcDbTable)',
      desc: 'Tạo bảng tổng hợp khối lượng đào đắp chuẩn SNVN VI.1.3 trực tiếp trên Model Space.',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex h-[min(86vh,780px)] w-[min(1060px,96vw)] flex-col overflow-hidden rounded-xl border border-[#263248] bg-[#141B29] shadow-2xl">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#263248] px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <Plug className="h-4 w-4 text-sky-400" />
            <div>
              <h2 className="text-sm font-semibold text-slate-100">
                Cầu nối MCP hai chiều với AutoCAD 2022 (ActiveX COM &amp; ObjectARX)
              </h2>
              <p className="text-xs text-slate-400">{connectionInfo}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownloadKit}
              disabled={downloading}
              className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-60 whitespace-nowrap shrink-0"
            >
              <Download className="h-3.5 w-3.5" />
              {downloading ? 'Đang đóng gói...' : 'Tải trọn bộ Cầu nối (.ZIP)'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-1.5 text-slate-400 hover:bg-[#1C2538] hover:text-white"
              aria-label="Đóng"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center justify-between border-b border-[#263248] bg-[#0F1521] px-5 py-2">
          <div className="flex items-center gap-1 rounded-lg border border-[#263248] bg-[#0B0F17] p-1">
            {[
              { id: 'tools', label: 'Điều khiển & Kiểm thử MCP' },
              { id: 'python', label: 'Python ActiveX COM (.py)' },
              { id: 'csharp', label: 'C# .NET ObjectARX (.cs)' },
              { id: 'guide', label: 'Hướng dẫn triển khai local' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id as ModalTab)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
                  tab === t.id
                    ? 'bg-sky-500/20 text-sky-300'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 text-xs">
            <label className="flex items-center gap-2 text-slate-300">
              <input
                type="checkbox"
                checked={useSandbox}
                onChange={(e) => onUseSandboxChange(e.target.checked)}
                className="h-3.5 w-3.5 accent-sky-500"
              />
              <span>Chế độ Mô phỏng (Sandbox)</span>
            </label>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {tab === 'tools' && (
            <div className="space-y-5">
              {/* Endpoint Bar */}
              <div className="flex flex-wrap items-end gap-3 rounded-lg border border-[#263248] bg-[#0F1521] p-3.5 text-xs">
                <div className="flex-1 min-w-[260px]">
                  <label className="mb-1 block text-[11px] text-slate-400">
                    Địa chỉ cổng MCP cục bộ (Python ActiveX hoặc C# ObjectARX trên Windows)
                  </label>
                  <input
                    type="text"
                    value={endpoint}
                    onChange={(e) => onEndpointChange(e.target.value)}
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-3 py-1.5 font-mono text-xs text-sky-300 focus:border-sky-500 focus:outline-none"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => onRunTool('autocad_ping')}
                  className="flex items-center gap-1.5 rounded-md bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-sky-500 whitespace-nowrap shrink-0"
                >
                  <Play className="h-3.5 w-3.5" />
                  Kiểm tra kết nối (Ping)
                </button>
              </div>

              {/* 7 MCP Tools Grid */}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {mcpTools.map((tool) => (
                  <div
                    key={tool.name}
                    className="flex items-start justify-between gap-3 rounded-lg border border-[#263248] bg-[#0F1521] p-3.5"
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-slate-100">{tool.title}</div>
                      <div className="mt-0.5 font-mono text-[11px] text-sky-400">{tool.name}</div>
                      <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{tool.desc}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRunTool(tool.name)}
                      className="flex items-center gap-1 rounded-md border border-[#263248] bg-[#1C2538] px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:border-sky-500/50 hover:text-white whitespace-nowrap shrink-0"
                    >
                      <Play className="h-3 w-3 text-sky-400" />
                      Chạy
                    </button>
                  </div>
                ))}
              </div>

              {/* JSON-RPC Inspector Log */}
              <div className="rounded-lg border border-[#263248] bg-[#0B0F17]">
                <div className="flex items-center justify-between border-b border-[#263248] px-3.5 py-2 text-xs">
                  <span className="flex items-center gap-1.5 font-semibold text-slate-200">
                    <Terminal className="h-3.5 w-3.5 text-sky-400" />
                    Nhật ký giao thức JSON-RPC 2.0 / MCP ({logs.length})
                  </span>
                </div>
                <div className="max-h-56 overflow-y-auto divide-y divide-[#1E293B] font-mono text-[11px]">
                  {logs.length === 0 ? (
                    <div className="p-4 text-center font-sans text-slate-500">
                      Nhấn vào bất kỳ công cụ MCP nào phía trên để gửi lệnh JSON-RPC 2.0 tới AutoCAD 2022 hoặc chế độ Mô phỏng.
                    </div>
                  ) : (
                    logs.map((entry) => (
                      <div key={entry.id} className="p-3 space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-slate-400">
                            {entry.timestamp} · <strong className="text-sky-300">{entry.method}</strong>
                          </span>
                          <span
                            className={
                              entry.status === 'ok' ? 'text-emerald-400' : 'text-red-400'
                            }
                          >
                            {entry.status === 'ok' ? 'Thành công' : 'Lỗi kết nối'} ·{' '}
                            {entry.mode === 'live' ? 'Live' : 'Sandbox'}
                          </span>
                        </div>
                        <div className="font-sans text-slate-300">{entry.summary}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {tab === 'python' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <Code2 className="h-4 w-4 text-emerald-400" />
                  <span className="font-mono font-semibold">python_activex/snvn_autocad_mcp.py</span>
                  <span className="text-slate-500">· FastAPI + win32com (AutoCAD.Application.24.1)</span>
                </div>
                <button
                  type="button"
                  onClick={() => copyCode('py', PYTHON_ACTIVEX_MCP_CODE)}
                  className="flex items-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-3 py-1.5 text-xs font-medium text-slate-200 hover:text-white"
                >
                  {copiedKey === 'py' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  {copiedKey === 'py' ? 'Đã sao chép' : 'Sao chép mã Python'}
                </button>
              </div>
              <pre className="max-h-[420px] overflow-auto rounded-lg border border-[#263248] bg-[#0B0F17] p-4 font-mono text-[11px] leading-relaxed text-slate-200">
                {PYTHON_ACTIVEX_MCP_CODE}
              </pre>
              <div className="rounded-lg border border-[#263248] bg-[#0F1521] p-3 text-xs">
                <div className="mb-1 font-mono text-[11px] text-slate-400">requirements.txt</div>
                <pre className="font-mono text-[11px] text-emerald-300">{PYTHON_REQUIREMENTS_TXT}</pre>
              </div>
            </div>
          )}

          {tab === 'csharp' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <Code2 className="h-4 w-4 text-sky-400" />
                  <span className="font-mono font-semibold">csharp_objectarx/SnvnMcpPlugin.cs</span>
                  <span className="text-slate-500">· .NET Framework 4.8 + ObjectARX 2022</span>
                </div>
                <button
                  type="button"
                  onClick={() => copyCode('cs', CSHARP_OBJECTARX_CODE)}
                  className="flex items-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-3 py-1.5 text-xs font-medium text-slate-200 hover:text-white"
                >
                  {copiedKey === 'cs' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  {copiedKey === 'cs' ? 'Đã sao chép' : 'Sao chép mã C#'}
                </button>
              </div>
              <pre className="max-h-[400px] overflow-auto rounded-lg border border-[#263248] bg-[#0B0F17] p-4 font-mono text-[11px] leading-relaxed text-slate-200">
                {CSHARP_OBJECTARX_CODE}
              </pre>
              <div className="rounded-lg border border-[#263248] bg-[#0F1521] p-3 text-xs">
                <div className="mb-1 font-mono text-[11px] text-slate-400">SnvnMcpPlugin.csproj</div>
                <pre className="font-mono text-[11px] text-sky-300">{CSHARP_CSPROJ_CODE}</pre>
              </div>
            </div>
          )}

          {tab === 'guide' && (
            <div className="rounded-lg border border-[#263248] bg-[#0B0F17] p-5">
              <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-slate-300">
                {BRIDGE_README_MD}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
