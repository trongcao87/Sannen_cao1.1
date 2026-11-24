import JSZip from 'jszip';

export const PYTHON_ACTIVEX_MCP_CODE = `"""
SNVN Studio — AutoCAD 2022 ActiveX COM MCP Server
Yêu cầu: Windows + AutoCAD 2022 + Python 3.10+
Cài đặt: pip install fastapi uvicorn pywin32 pydantic
Chạy:    python snvn_autocad_mcp.py
"""
import math
import pythoncom
import win32com.client
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="SNVN AutoCAD 2022 ActiveX MCP Bridge", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = 1
    method: str
    params: Optional[Dict[str, Any]] = None


def get_acad_doc():
    pythoncom.CoInitialize()
    # ProgID của AutoCAD 2022 là AutoCAD.Application.24.1 (fallback AutoCAD.Application)
    try:
        acad = win32com.client.GetActiveObject("AutoCAD.Application.24.1")
    except Exception:
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
    return acad, acad.ActiveDocument


def ensure_layer(doc, name: str, color_aci: int = 7):
    try:
        layer = doc.Layers.Item(name)
    except Exception:
        layer = doc.Layers.Add(name)
    layer.color = color_aci
    return layer


def pt3(x: float, y: float, z: float = 0.0):
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (float(x), float(y), float(z)))


def tool_ping() -> Dict[str, Any]:
    acad, doc = get_acad_doc()
    layers = [doc.Layers.Item(i).Name for i in range(doc.Layers.Count)]
    return {
        "engine": "Python ActiveX COM (win32com)",
        "acadVersion": acad.Version,
        "drawingName": doc.Name,
        "entityCount": doc.ModelSpace.Count,
        "layers": layers[:80],
    }


def tool_read_survey_entities(params: Dict[str, Any]) -> Dict[str, Any]:
    """Đọc 6 loại đối tượng chuẩn SNVN (Chương III.1.1): Point, Block, Text, Line, 2DPoly, 3DPoly"""
    _, doc = get_acad_doc()
    ms = doc.ModelSpace
    allowed_layers = set(params.get("layers", []))
    allowed_types = set(params.get("entityTypes", ["POINT", "BLOCK", "TEXT", "LINE", "POLYLINE2D", "POLYLINE3D"]))

    points: List[Dict[str, Any]] = []
    breaklines: List[Dict[str, Any]] = []
    pt_idx = 1
    bl_idx = 1

    for ent in ms:
        try:
            layer = ent.Layer
            if allowed_layers and layer not in allowed_layers:
                continue
            ename = ent.EntityName

            if ename == "AcDbPoint" and "POINT" in allowed_types:
                c = ent.Coordinates
                points.append({"id": f"CAD-PT-{pt_idx}", "x": c[0], "y": c[1], "z": c[2], "source": "POINT", "layer": layer})
                pt_idx += 1

            elif ename == "AcDbBlockReference" and "BLOCK" in allowed_types:
                c = ent.InsertionPoint
                points.append({"id": f"CAD-BK-{pt_idx}", "x": c[0], "y": c[1], "z": c[2], "source": "BLOCK", "layer": layer})
                pt_idx += 1

            elif ename in ("AcDbText", "AcDbMText") and "TEXT" in allowed_types:
                c = ent.InsertionPoint
                raw = str(ent.TextString).strip().replace(",", ".")
                try:
                    z_val = float(raw)
                except ValueError:
                    z_val = 0.0
                points.append({"id": f"CAD-TX-{pt_idx}", "x": c[0], "y": c[1], "z": z_val, "source": "TEXT", "layer": layer, "label": raw})
                pt_idx += 1

            elif ename == "AcDbLine" and "LINE" in allowed_types:
                s, e = ent.StartPoint, ent.EndPoint
                breaklines.append({
                    "id": f"CAD-BL-{bl_idx}",
                    "name": f"Line ({layer})",
                    "is3D": True,
                    "layer": layer,
                    "vertices": [{"x": s[0], "y": s[1], "z": s[2]}, {"x": e[0], "y": e[1], "z": e[2]}],
                })
                bl_idx += 1

            elif ename == "AcDbPolyline" and "POLYLINE2D" in allowed_types:
                coords = list(ent.Coordinates)
                elev = float(ent.Elevation)
                verts = [{"x": coords[i], "y": coords[i + 1], "z": elev} for i in range(0, len(coords), 2)]
                if len(verts) >= 2:
                    breaklines.append({"id": f"CAD-BL2D-{bl_idx}", "name": f"2DPoly ({layer})", "is3D": False, "layer": layer, "vertices": verts})
                    bl_idx += 1

            elif ename == "AcDb3dPolyline" and "POLYLINE3D" in allowed_types:
                coords = list(ent.Coordinates)
                verts = [{"x": coords[i], "y": coords[i + 1], "z": coords[i + 2]} for i in range(0, len(coords), 3)]
                if len(verts) >= 2:
                    breaklines.append({"id": f"CAD-BL3D-{bl_idx}", "name": f"3DPoly ({layer})", "is3D": True, "layer": layer, "vertices": verts})
                    bl_idx += 1
        except Exception:
            continue

    return {"points": points, "breaklines": breaklines, "totalRead": len(points) + len(breaklines)}


def tool_read_boundaries(params: Dict[str, Any]) -> Dict[str, Any]:
    _, doc = get_acad_doc()
    boundary_layer = params.get("boundaryLayer", "SNVN_BIEN")
    excl_layer = params.get("exclusionLayer", "SNVN_VUNG_BOQUA")
    boundary = None
    exclusions = []

    for ent in doc.ModelSpace:
        if ent.EntityName == "AcDbPolyline" and ent.Closed:
            coords = list(ent.Coordinates)
            verts = [{"x": coords[i], "y": coords[i + 1]} for i in range(0, len(coords), 2)]
            if ent.Layer == boundary_layer and boundary is None:
                boundary = {"id": "CAD-BND", "name": f"Biên ({boundary_layer})", "type": "boundary", "vertices": verts}
            elif ent.Layer == excl_layer:
                exclusions.append({"id": f"CAD-EXC-{len(exclusions)+1}", "name": f"Bỏ qua ({excl_layer})", "type": "exclusion", "vertices": verts})

    return {"boundary": boundary, "exclusions": exclusions}


def tool_draw_grid_results(params: Dict[str, Any]) -> Dict[str, Any]:
    _, doc = get_acad_doc()
    ms = doc.ModelSpace
    ensure_layer(doc, "SNVN_LUOI", 7)
    ensure_layer(doc, "SNVN_DAO", 2)
    ensure_layer(doc, "SNVN_DAP", 1)
    ensure_layer(doc, "SNVN_RANHGIOI_0", 4)
    ensure_layer(doc, "SNVN_NUT_TN", 3)
    ensure_layer(doc, "SNVN_NUT_TK", 1)
    ensure_layer(doc, "SNVN_NUT_DH", 2)

    drawn = 0
    for cell in params.get("cells", []):
        corners = cell.get("corners", [])
        if len(corners) == 4:
            for i in range(4):
                a, b = corners[i], corners[(i + 1) % 4]
                ln = ms.AddLine(pt3(a["x"], a["y"]), pt3(b["x"], b["y"]))
                ln.Layer = "SNVN_LUOI"
                drawn += 1
        for sub in cell.get("subPolygons", []):
            layer = "SNVN_DAP" if sub["type"] == "fill" else "SNVN_DAO"
            c = sub["centroid"]
            r = min(4.2, max(2.0, math.sqrt(max(sub["area"], 1)) * 0.22))
            cir = ms.AddCircle(pt3(c["x"], c["y"]), r)
            cir.Layer = layer
            t_vol = ms.AddText(f'{sub["volume"]:.1f}', pt3(c["x"] - r * 0.55, c["y"] - r * 0.55), 0.95)
            t_vol.Layer = layer
            drawn += 2

    for seg in params.get("zeroLines", []):
        ln = ms.AddLine(pt3(seg["p1"]["x"], seg["p1"]["y"]), pt3(seg["p2"]["x"], seg["p2"]["y"]))
        ln.Layer = "SNVN_RANHGIOI_0"
        drawn += 1

    for node in params.get("nodes", []):
        t1 = ms.AddText(f'{node["hTN"]:.2f}', pt3(node["x"] - 4.0, node["y"] + 0.5), 0.9)
        t1.Layer = "SNVN_NUT_TN"
        t2 = ms.AddText(f'{node["hTK"]:.2f}', pt3(node["x"] + 0.5, node["y"] + 0.5), 0.9)
        t2.Layer = "SNVN_NUT_TK"
        t3 = ms.AddText(f'{abs(node["deltaH"]):.2f}', pt3(node["x"] - 4.0, node["y"] - 1.3), 0.9)
        t3.Layer = "SNVN_NUT_DH"
        drawn += 3

    doc.Regen(1)
    return {"drawnEntities": drawn, "status": "Đã vẽ xong lưới san nền SNVN lên AutoCAD 2022"}


def tool_draw_contours_taluy(params: Dict[str, Any]) -> Dict[str, Any]:
    _, doc = get_acad_doc()
    ms = doc.ModelSpace
    ensure_layer(doc, "SNVN_DONGMUC_CAI", 30)
    ensure_layer(doc, "SNVN_DONGMUC_CON", 8)
    ensure_layer(doc, "SNVN_TALUY_DAO", 2)
    ensure_layer(doc, "SNVN_TALUY_DAP", 1)

    drawn = 0
    for c in params.get("contours", []):
        pts = c.get("points", [])
        if len(pts) < 2:
            continue
        flat = []
        for p in pts:
            flat.extend([float(p["x"]), float(p["y"])])
        arr = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, flat)
        pl = ms.AddLightWeightPolyline(arr)
        pl.Elevation = float(c["elevation"])
        pl.Layer = "SNVN_DONGMUC_CAI" if c.get("isMajor") else "SNVN_DONGMUC_CON"
        drawn += 1

    for tk in params.get("taluyTicks", []):
        ln = ms.AddLine(pt3(tk["p1"]["x"], tk["p1"]["y"]), pt3(tk["p2"]["x"], tk["p2"]["y"]))
        ln.Layer = "SNVN_TALUY_DAP" if tk["type"] == "fill" else "SNVN_TALUY_DAO"
        drawn += 1

    doc.Regen(1)
    return {"drawnEntities": drawn, "status": "Đã vẽ đường đồng mức và ký hiệu Taluy 2D"}


def tool_draw_cross_section(params: Dict[str, Any]) -> Dict[str, Any]:
    _, doc = get_acad_doc()
    ms = doc.ModelSpace
    ensure_layer(doc, "SNVN_MC_TN", 3)
    ensure_layer(doc, "SNVN_MC_TK", 1)
    ensure_layer(doc, "SNVN_MC_BANG", 7)

    ox = float(params.get("insertX", 0.0))
    oy = float(params.get("insertY", -150.0))
    datum = float(params.get("datumElevation", 0.0))
    scale_y = float(params.get("verticalExaggeration", 5.0))
    stations = params.get("stations", [])

    drawn = 0
    for i in range(len(stations) - 1):
        s1, s2 = stations[i], stations[i + 1]
        l_tn = ms.AddLine(
            pt3(ox + s1["dist"], oy + (s1["hTN"] - datum) * scale_y),
            pt3(ox + s2["dist"], oy + (s2["hTN"] - datum) * scale_y),
        )
        l_tn.Layer = "SNVN_MC_TN"
        l_tk = ms.AddLine(
            pt3(ox + s1["dist"], oy + (s1["hTK"] - datum) * scale_y),
            pt3(ox + s2["dist"], oy + (s2["hTK"] - datum) * scale_y),
        )
        l_tk.Layer = "SNVN_MC_TK"
        drawn += 2

    doc.Regen(1)
    return {"drawnEntities": drawn, "status": "Đã vẽ mặt cắt ngang chuẩn TCVN"}


def tool_insert_snvn_tables(params: Dict[str, Any]) -> Dict[str, Any]:
    _, doc = get_acad_doc()
    ms = doc.ModelSpace
    ensure_layer(doc, "SNVN_BANG", 7)
    rows = params.get("rows", [])
    ox = float(params.get("insertX", 280.0))
    oy = float(params.get("insertY", 180.0))

    table = ms.AddTable(pt3(ox, oy), len(rows) + 1, 3, 6.0, 42.0)
    table.Layer = "SNVN_BANG"
    table.SetText(0, 0, params.get("title", "BẢNG TỔNG HỢP KHỐI LƯỢNG SAN NỀN"))
    for idx, r in enumerate(rows):
        table.SetText(idx + 1, 0, str(r["label"]))
        table.SetText(idx + 1, 1, str(r["unit"]))
        table.SetText(idx + 1, 2, f'{float(r["value"]):.2f}')
    doc.Regen(1)
    return {"insertedRows": len(rows), "status": "Đã chèn bảng khối lượng chuẩn SNVN"}


TOOLS = {
    "autocad_ping": lambda p: tool_ping(),
    "autocad_read_survey_entities": tool_read_survey_entities,
    "autocad_read_boundaries": tool_read_boundaries,
    "autocad_draw_grid_results": tool_draw_grid_results,
    "autocad_draw_contours_taluy": tool_draw_contours_taluy,
    "autocad_draw_cross_section": tool_draw_cross_section,
    "autocad_insert_snvn_tables": tool_insert_snvn_tables,
}


@app.post("/mcp")
def handle_mcp(req: JsonRpcRequest):
    try:
        if req.method == "tools/list":
            return {"jsonrpc": "2.0", "id": req.id, "result": {"tools": list(TOOLS.keys())}}
        tool_name = req.method
        tool_params = req.params or {}
        if req.method == "tools/call":
            tool_name = tool_params.get("name", "")
            tool_params = tool_params.get("arguments", {})
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}
        result = TOOLS[tool_name](tool_params)
        return {"jsonrpc": "2.0", "id": req.id, "result": result}
    except Exception as ex:
        return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32000, "message": str(ex)}}


if __name__ == "__main__":
    import uvicorn
    print("SNVN AutoCAD 2022 ActiveX MCP Server đang chạy tại http://127.0.0.1:8765/mcp")
    uvicorn.run(app, host="127.0.0.1", port=8765)
`;

export const CSHARP_OBJECTARX_CODE = `// SNVN Studio — AutoCAD 2022 .NET ObjectARX MCP Plugin
// Target: .NET Framework 4.8 | AutoCAD 2022 ObjectARX SDK (accoremgd, acdbmgd, acmgd)
// Lệnh trong AutoCAD 2022: NETLOAD -> SnvnMcpPlugin.dll -> gõ SNVN_MCP_START

using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;

[assembly: CommandClass(typeof(SnvnMcpPlugin.SnvnMcpCommands))]

namespace SnvnMcpPlugin
{
    public class SnvnMcpCommands
    {
        private static HttpListener _listener;
        private static CancellationTokenSource _cts;
        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 64 * 1024 * 1024 };

        [CommandMethod("SNVN_MCP_START")]
        public void StartMcpBridge()
        {
            var ed = Application.DocumentManager.MdiActiveDocument.Editor;
            if (_listener != null && _listener.IsListening)
            {
                ed.WriteMessage("\\n[SNVN MCP] Cầu nối ObjectARX đang chạy tại http://127.0.0.1:8765/mcp");
                return;
            }

            _cts = new CancellationTokenSource();
            _listener = new HttpListener();
            _listener.Prefixes.Add("http://127.0.0.1:8765/");
            _listener.Start();
            Task.Run(() => ListenLoopAsync(_cts.Token));
            ed.WriteMessage("\\n[SNVN MCP] Đã khởi động cầu nối ObjectARX AutoCAD 2022 tại http://127.0.0.1:8765/mcp");
        }

        [CommandMethod("SNVN_MCP_STOP")]
        public void StopMcpBridge()
        {
            _cts?.Cancel();
            _listener?.Stop();
            _listener = null;
            Application.DocumentManager.MdiActiveDocument.Editor.WriteMessage("\\n[SNVN MCP] Đã dừng cầu nối ObjectARX.");
        }

        private static async Task ListenLoopAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener != null && _listener.IsListening)
            {
                HttpListenerContext ctx;
                try { ctx = await _listener.GetContextAsync(); }
                catch { break; }

                ctx.Response.AddHeader("Access-Control-Allow-Origin", "*");
                ctx.Response.AddHeader("Access-Control-Allow-Headers", "Content-Type");
                ctx.Response.AddHeader("Access-Control-Allow-Methods", "POST, OPTIONS");

                if (ctx.Request.HttpMethod == "OPTIONS")
                {
                    ctx.Response.StatusCode = 204;
                    ctx.Response.Close();
                    continue;
                }

                string body;
                using (var reader = new StreamReader(ctx.Request.InputStream, Encoding.UTF8))
                    body = await reader.ReadToEndAsync();

                var req = Json.Deserialize<Dictionary<string, object>>(body);
                var reqId = req.ContainsKey("id") ? req["id"] : 1;
                var method = req.ContainsKey("method") ? Convert.ToString(req["method"]) : "";
                var rpcParams = req.ContainsKey("params") ? req["params"] as Dictionary<string, object> : new Dictionary<string, object>();

                if (method == "tools/call" && rpcParams != null)
                {
                    method = Convert.ToString(rpcParams["name"]);
                    rpcParams = rpcParams.ContainsKey("arguments") ? rpcParams["arguments"] as Dictionary<string, object> : new Dictionary<string, object>();
                }

                object payload;
                try
                {
                    // Điều phối an toàn sang luồng chính của AutoCAD 2022 bằng ExecuteInCommandContextAsync
                    object toolRes = null;
                    Exception toolEx = null;
                    await Application.DocumentManager.ExecuteInCommandContextAsync(async _ =>
                    {
                        try { toolRes = ExecuteToolOnAcadThread(method, rpcParams ?? new Dictionary<string, object>()); }
                        catch (Exception ex) { toolEx = ex; }
                        await Task.CompletedTask;
                    }, null);

                    if (toolEx != null) throw toolEx;
                    payload = new Dictionary<string, object> { { "jsonrpc", "2.0" }, { "id", reqId }, { "result", toolRes } };
                }
                catch (Exception ex)
                {
                    payload = new Dictionary<string, object>
                    {
                        { "jsonrpc", "2.0" },
                        { "id", reqId },
                        { "error", new Dictionary<string, object> { { "code", -32000 }, { "message", ex.Message } } }
                    };
                }

                var bytes = Encoding.UTF8.GetBytes(Json.Serialize(payload));
                ctx.Response.ContentType = "application/json; charset=utf-8";
                await ctx.Response.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                ctx.Response.Close();
            }
        }

        private static object ExecuteToolOnAcadThread(string method, Dictionary<string, object> args)
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            var db = doc.Database;

            using (doc.LockDocument())
            using (var tr = db.TransactionManager.StartTransaction())
            {
                var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                var btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                if (method == "autocad_ping")
                {
                    var lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
                    var layers = new List<string>();
                    foreach (ObjectId lid in lt)
                    {
                        var ltr = (LayerTableRecord)tr.GetObject(lid, OpenMode.ForRead);
                        layers.Add(ltr.Name);
                    }
                    tr.Commit();
                    return new
                    {
                        engine = "C# .NET ObjectARX 2022",
                        acadVersion = Application.Version.ToString(),
                        drawingName = doc.Name,
                        layers
                    };
                }

                if (method == "autocad_read_survey_entities")
                {
                    var points = new List<object>();
                    var breaklines = new List<object>();
                    int ptIdx = 1, blIdx = 1;

                    foreach (ObjectId oid in btr)
                    {
                        var ent = tr.GetObject(oid, OpenMode.ForRead) as Entity;
                        if (ent == null) continue;

                        if (ent is DBPoint pt)
                        {
                            points.Add(new { id = $"ARX-PT-{ptIdx++}", x = pt.Position.X, y = pt.Position.Y, z = pt.Position.Z, source = "POINT", layer = pt.Layer });
                        }
                        else if (ent is BlockReference blk)
                        {
                            points.Add(new { id = $"ARX-BK-{ptIdx++}", x = blk.Position.X, y = blk.Position.Y, z = blk.Position.Z, source = "BLOCK", layer = blk.Layer });
                        }
                        else if (ent is DBText txt)
                        {
                            double.TryParse(txt.TextString.Replace(',', '.'), out double zVal);
                            points.Add(new { id = $"ARX-TX-{ptIdx++}", x = txt.Position.X, y = txt.Position.Y, z = zVal, source = "TEXT", layer = txt.Layer, label = txt.TextString });
                        }
                        else if (ent is Line ln)
                        {
                            breaklines.Add(new
                            {
                                id = $"ARX-LN-{blIdx++}",
                                name = $"Line ({ln.Layer})",
                                is3D = true,
                                layer = ln.Layer,
                                vertices = new[]
                                {
                                    new { x = ln.StartPoint.X, y = ln.StartPoint.Y, z = ln.StartPoint.Z },
                                    new { x = ln.EndPoint.X, y = ln.EndPoint.Y, z = ln.EndPoint.Z }
                                }
                            });
                        }
                        else if (ent is Polyline pl2d && pl2d.NumberOfVertices >= 2)
                        {
                            var verts = new List<object>();
                            for (int i = 0; i < pl2d.NumberOfVertices; i++)
                            {
                                var p2 = pl2d.GetPoint2dAt(i);
                                verts.Add(new { x = p2.X, y = p2.Y, z = pl2d.Elevation });
                            }
                            breaklines.Add(new { id = $"ARX-2D-{blIdx++}", name = $"2DPoly ({pl2d.Layer})", is3D = false, layer = pl2d.Layer, vertices = verts });
                        }
                        else if (ent is Polyline3d pl3d)
                        {
                            var verts = new List<object>();
                            foreach (ObjectId vid in pl3d)
                            {
                                var v = (PolylineVertex3d)tr.GetObject(vid, OpenMode.ForRead);
                                verts.Add(new { x = v.Position.X, y = v.Position.Y, z = v.Position.Z });
                            }
                            if (verts.Count >= 2)
                                breaklines.Add(new { id = $"ARX-3D-{blIdx++}", name = $"3DPoly ({pl3d.Layer})", is3D = true, layer = pl3d.Layer, vertices = verts });
                        }
                    }
                    tr.Commit();
                    return new { points, breaklines, totalRead = points.Count + breaklines.Count };
                }

                if (method == "autocad_draw_grid_results")
                {
                    EnsureLayer(db, tr, "SNVN_LUOI", 7);
                    EnsureLayer(db, tr, "SNVN_RANHGIOI_0", 4);
                    int drawn = 0;
                    if (args.ContainsKey("zeroLines") && args["zeroLines"] is System.Collections.ArrayList zList)
                    {
                        foreach (Dictionary<string, object> seg in zList)
                        {
                            var p1 = seg["p1"] as Dictionary<string, object>;
                            var p2 = seg["p2"] as Dictionary<string, object>;
                            var line = new Line(
                                new Point3d(Convert.ToDouble(p1["x"]), Convert.ToDouble(p1["y"]), 0),
                                new Point3d(Convert.ToDouble(p2["x"]), Convert.ToDouble(p2["y"]), 0)
                            ) { Layer = "SNVN_RANHGIOI_0" };
                            btr.AppendEntity(line);
                            tr.AddNewlyCreatedDBObject(line, true);
                            drawn++;
                        }
                    }
                    tr.Commit();
                    return new { drawnEntities = drawn, status = "ObjectARX Transaction hoàn tất" };
                }

                tr.Commit();
                return new { status = $"Đã thực thi {method} qua ObjectARX 2022" };
            }
        }

        private static void EnsureLayer(Database db, Transaction tr, string layerName, short colorIndex)
        {
            var lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForWrite);
            if (!lt.Has(layerName))
            {
                var ltr = new LayerTableRecord
                {
                    Name = layerName,
                    Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex)
                };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }
        }
    }
}
`;

export const CSHARP_CSPROJ_CODE = `<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework>
    <PlatformTarget>x64</PlatformTarget>
    <AutoCAD2022Path>C:\\Program Files\\Autodesk\\AutoCAD 2022</AutoCAD2022Path>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="accoremgd">
      <HintPath>$(AutoCAD2022Path)\\accoremgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="acdbmgd">
      <HintPath>$(AutoCAD2022Path)\\acdbmgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="acmgd">
      <HintPath>$(AutoCAD2022Path)\\acmgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="System.Web.Extensions" />
  </ItemGroup>
</Project>
`;

export const PYTHON_REQUIREMENTS_TXT = `fastapi>=0.111.0
uvicorn>=0.30.0
pywin32>=306
pydantic>=2.7.0
`;

export const START_BAT_CODE = `@echo off
echo === Khoi dong SNVN AutoCAD 2022 ActiveX MCP Server ===
pip install -r requirements.txt
python snvn_autocad_mcp.py
pause
`;

export const BRIDGE_README_MD = `# Bộ Cầu nối MCP AutoCAD 2022 cho SNVN Studio

Gói này bao gồm cả 2 phương án kết nối cục bộ với **AutoCAD 2022 (Windows 64-bit)**:

## Phương án 1: Python ActiveX COM (Nhanh, không cần Visual Studio)
1. Mở bản vẽ trắc địa DWG trên **AutoCAD 2022**.
2. Giải nén thư mục \`python_activex/\`, chạy tệp \`start_mcp_bridge.bat\` (hoặc \`pip install -r requirements.txt && python snvn_autocad_mcp.py\`).
3. Máy chủ MCP sẽ mở cổng tại \`http://127.0.0.1:8765/mcp\`.
4. Quay lại ứng dụng web **SNVN Studio**, mở **Cầu nối AutoCAD MCP** và nhấn **Kiểm tra kết nối**.

## Phương án 2: C# .NET ObjectARX Plugin (Hiệu năng cao nội tuyến AutoCAD)
1. Mở thư mục \`csharp_objectarx/\` bằng Visual Studio 2022 hoặc chạy \`dotnet build -c Release\`.
2. Đảm bảo đường dẫn \`AutoCAD2022Path\` trong \`SnvnMcpPlugin.csproj\` trỏ đúng thư mục cài AutoCAD 2022.
3. Trong AutoCAD 2022, gõ lệnh \`NETLOAD\`, chọn \`SnvnMcpPlugin.dll\`.
4. Gõ lệnh \`SNVN_MCP_START\` trên Command Line của AutoCAD 2022.
5. Kết nối từ ứng dụng web **SNVN Studio** tại \`http://127.0.0.1:8765/mcp\`.
`;

/** Bundle both Python ActiveX and C# ObjectARX bridges into a single downloadable .zip kit */
export async function downloadAutoCadBridgeZip(): Promise<void> {
  const zip = new JSZip();
  zip.file('README.md', BRIDGE_README_MD);

  const pyDir = zip.folder('python_activex');
  pyDir?.file('snvn_autocad_mcp.py', PYTHON_ACTIVEX_MCP_CODE);
  pyDir?.file('requirements.txt', PYTHON_REQUIREMENTS_TXT);
  pyDir?.file('start_mcp_bridge.bat', START_BAT_CODE);

  const csDir = zip.folder('csharp_objectarx');
  csDir?.file('SnvnMcpPlugin.cs', CSHARP_OBJECTARX_CODE);
  csDir?.file('SnvnMcpPlugin.csproj', CSHARP_CSPROJ_CODE);

  const blob = await zip.generateAsync({ type: 'blob' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'SNVN_AutoCAD2022_MCP_Bridge_Kit.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
