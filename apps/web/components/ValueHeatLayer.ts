// Per-pixel exact value heat as a MapLibre custom layer (built from
// scratch, no reference to the previous renderer).
//
// Technique: the scored field lives in a data-space RGBA texture (lon/lat
// grid, color + coverage alpha). Every screen pixel is shaded on the GPU:
// viewport -> lon/lat -> grid lookup, at full drawing-buffer resolution
// (devicePixelRatio-exact on every zoom). No kernel-density pileup, no
// blurry upscale, no float-texture extensions. Zero-weight areas are
// discarded, so the base map shows through where there is no data.

import type { CustomLayerInterface, Map as MLMap } from "maplibre-gl";

const VERT = `
attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

const FRAG = `
precision mediump float;
varying vec2 v_uv;
uniform sampler2D u_grid;
uniform vec4 u_view;    // visible minlon, minlat, maxlon, maxlat (degrees)
uniform vec4 u_gridBox; // texture grid bbox, same order
uniform float u_opacity;
void main() {
  vec2 lonlat = mix(u_view.xy, u_view.zw, v_uv);
  vec2 guv = (lonlat - u_gridBox.xy) / (u_gridBox.zw - u_gridBox.xy);
  if (guv.x < 0.0 || guv.x > 1.0 || guv.y < 0.0 || guv.y > 1.0) discard;
  vec4 tex = texture2D(u_grid, guv);
  if (tex.a < 0.004) discard;
  gl_FragColor = vec4(tex.rgb, tex.a * u_opacity);
}
`;

function compile(gl: WebGLRenderingContext, type: number, src: string): WebGLShader {
  const sh = gl.createShader(type);
  if (!sh) throw new Error("value-heat: shader alloc failed");
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    throw new Error(`value-heat: ${gl.getShaderInfoLog(sh)}`);
  }
  return sh;
}

export class ValueHeatLayer implements CustomLayerInterface {
  id: string;
  type = "custom" as const;
  renderingMode = "2d" as const;

  private map: MLMap | null = null;
  private gl: WebGLRenderingContext | null = null;
  private prog: WebGLProgram | null = null;
  private buf: WebGLBuffer | null = null;
  private tex: WebGLTexture | null = null;
  private texCols = 0;
  private texRows = 0;
  private gridBox: [number, number, number, number] = [0, 0, 0, 0];
  private hasData = false;
  private opacity: number;

  constructor(id = "value-heat", opacity = 1) {
    this.id = id;
    this.opacity = opacity;
  }

  onAdd(map: MLMap, gl: WebGLRenderingContext): void {
    this.map = map;
    this.gl = gl;
    const prog = gl.createProgram();
    if (!prog) throw new Error("value-heat: program alloc failed");
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      throw new Error("value-heat: link failed");
    }
    this.prog = prog;
    const buf = gl.createBuffer();
    this.buf = buf;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.tex = tex;
  }

  /** Upload a fresh field; empty data clears the map (honest gaps). */
  setField(
    rgba: Uint8ClampedArray | null,
    cols: number,
    rows: number,
    bbox: [number, number, number, number],
  ): void {
    // Called before onAdd (data arrived first): stash until GL exists.
    if (!this.gl || !this.tex || !this.prog) {
      if (rgba) {
        this.pending = { rgba, cols, rows, bbox };
        this.hasData = true;
      } else {
        this.pending = null;
        this.hasData = false;
      }
      return;
    }
    this.upload(this.gl, rgba, cols, rows, bbox);
    // A texture upload alone schedules no frame: without this, new (or
    // cleared) data sits invisible on an idle map until the next pan/zoom.
    this.map?.triggerRepaint();
  }

  private pending: {
    rgba: Uint8ClampedArray;
    cols: number;
    rows: number;
    bbox: [number, number, number, number];
  } | null = null;

  private upload(
    gl: WebGLRenderingContext,
    rgba: Uint8ClampedArray | null,
    cols: number,
    rows: number,
    bbox: [number, number, number, number],
  ): void {
    if (!rgba || cols === 0 || rows === 0) {
      this.hasData = false;
      return;
    }
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, cols, rows, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);
    this.texCols = cols;
    this.texRows = rows;
    this.gridBox = bbox;
    this.hasData = true;
  }

  render(gl: WebGLRenderingContext): void {
    const map = this.map;
    if (!map || !this.prog || !this.tex || !this.hasData) return;
    if (this.pending) {
      const p = this.pending;
      this.pending = null;
      this.upload(gl, p.rgba, p.cols, p.rows, p.bbox);
    }
    const canvas = map.getCanvas();
    const nw = map.unproject([0, 0]);
    const se = map.unproject([canvas.clientWidth, canvas.clientHeight]);

    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(this.prog);
    const loc = (n: string) => gl.getUniformLocation(this.prog as WebGLProgram, n);
    gl.uniform4f(loc("u_view"), nw.lng, se.lat, se.lng, nw.lat);
    gl.uniform4f(
      loc("u_gridBox"),
      this.gridBox[0],
      this.gridBox[1],
      this.gridBox[2],
      this.gridBox[3],
    );
    gl.uniform1f(loc("u_opacity"), this.opacity);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.uniform1i(loc("u_grid"), 0);
    const apos = gl.getAttribLocation(this.prog, "a_pos");
    // Re-bind: MapLibre binds its own buffers between our onAdd and render.
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    gl.enableVertexAttribArray(apos);
    gl.vertexAttribPointer(apos, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.disableVertexAttribArray(apos);
    gl.disable(gl.BLEND);
  }

  onRemove(): void {
    if (this.gl) {
      if (this.tex) this.gl.deleteTexture(this.tex);
      if (this.prog) this.gl.deleteProgram(this.prog);
    }
    this.map = null;
    this.gl = null;
    this.tex = null;
    this.prog = null;
    this.hasData = false;
  }
}
