import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';

@Component({
  selector: 'app-neural-orb',
  template: `<canvas #canvas class="h-full w-full"></canvas>`,
})
export class NeuralOrbComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) private readonly canvasRef!: ElementRef<HTMLCanvasElement>;

  private rafId: number | null = null;
  private gl: WebGLRenderingContext | WebGL2RenderingContext | null = null;
  private program: WebGLProgram | null = null;
  private uTime: WebGLUniformLocation | null = null;
  private uRes: WebGLUniformLocation | null = null;

  ngAfterViewInit(): void {
    const canvas = this.canvasRef.nativeElement;
    const gl = (canvas.getContext('webgl2', { antialias: true }) ??
      canvas.getContext('webgl', { antialias: true })) as
      | WebGLRenderingContext
      | WebGL2RenderingContext
      | null;
    if (!gl) return;
    this.gl = gl;

    const vs = `
      attribute vec2 a_pos;
      void main(){ gl_Position = vec4(a_pos, 0.0, 1.0); }
    `;
    const fs = `
      precision highp float;
      uniform vec2 u_res;
      uniform float u_time;

      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453123); }
      vec2 hash2(vec2 p){
        return fract(sin(vec2(dot(p, vec2(127.1,311.7)), dot(p, vec2(269.5,183.3)))) * 43758.5453123);
      }

      vec2 starPos(vec2 cell){
        vec2 rnd = hash2(cell);
        return cell + rnd * 0.75 + 0.125;
      }

      float lineDist(vec2 p, vec2 a, vec2 b){
        vec2 ba = b - a;
        float h = clamp(dot(p - a, ba) / max(dot(ba, ba), 0.0001), 0.0, 1.0);
        return length((p - a) - ba * h);
      }

      vec2 starLayer(vec2 uv, float scale, float time){
        vec2 p = uv * scale;
        vec2 cell = floor(p);
        float stars = 0.0;
        float lines = 0.0;

        for (int y = -1; y <= 1; y++) {
          for (int x = -1; x <= 1; x++) {
            vec2 id = cell + vec2(float(x), float(y));
            vec2 sp = starPos(id);
            float d = length(p - sp);
            float strength = 0.35 + 0.65 * hash(id + 2.7);
            float twinkle = 0.95 + 0.05 * sin(time * 0.25 + hash(id) * 6.2831);
            float spark = 1.0 - smoothstep(0.0, 0.08, d);
            stars += pow(spark, 1.6) * strength * twinkle;
          }
        }

        vec2 s0 = starPos(cell);
        vec2 s1 = starPos(cell + vec2(1.0, 0.0));
        vec2 s2 = starPos(cell + vec2(0.0, 1.0));
        vec2 s3 = starPos(cell + vec2(1.0, 1.0));
        vec2 s4 = starPos(cell + vec2(-1.0, 1.0));

        float l1 = 1.0 - smoothstep(0.7, 1.4, length(s1 - s0));
        float l2 = 1.0 - smoothstep(0.7, 1.4, length(s2 - s0));
        float l3 = 1.0 - smoothstep(0.7, 1.4, length(s3 - s0));
        float l4 = 1.0 - smoothstep(0.7, 1.4, length(s4 - s0));

        float d1 = 1.0 - smoothstep(0.0, 0.05, lineDist(p, s0, s1));
        float d2 = 1.0 - smoothstep(0.0, 0.05, lineDist(p, s0, s2));
        float d3 = 1.0 - smoothstep(0.0, 0.05, lineDist(p, s0, s3));
        float d4 = 1.0 - smoothstep(0.0, 0.05, lineDist(p, s0, s4));

        lines += l1 * d1;
        lines += l2 * d2;
        lines += l3 * d3;
        lines += l4 * d4;

        return vec2(stars, lines);
      }

      void main(){
        vec2 uv = gl_FragCoord.xy / u_res.xy;
        vec2 p = uv - 0.5;
        p.x *= u_res.x / u_res.y;

        float vignette = smoothstep(1.2, 0.2, length(p));
        vec3 base = vec3(0.02, 0.03, 0.06) + vec3(0.04, 0.06, 0.1) * vignette;
        base += vec3(0.015, 0.025, 0.05) * (1.0 - uv.y);

        float driftT = u_time * 0.06;
        vec2 drift1 = vec2(sin(driftT), cos(driftT * 0.8)) * 0.035;
        vec2 drift2 = vec2(sin(driftT * 0.7 + 1.3), cos(driftT * 0.6 + 0.7)) * 0.05;

        vec2 layer1 = starLayer(p + drift1, 5.0, u_time);
        vec2 layer2 = starLayer(p + vec2(0.21, 0.15) + drift2, 9.0, u_time * 0.7);

        float stars = layer1.x * 0.55 + layer2.x * 0.25;
        float lines = layer1.y * 0.35 + layer2.y * 0.2;

        vec3 col = base;
        col += vec3(0.35, 0.55, 0.85) * lines * 0.35;
        col += vec3(0.8, 0.9, 1.0) * stars * 0.5;
        gl_FragColor = vec4(col, 1.0);
      }
    `;

    const program = this.createProgram(gl, vs, fs);
    if (!program) return;
    this.program = program;
    gl.useProgram(program);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(program, 'a_pos');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    this.uTime = gl.getUniformLocation(program, 'u_time');
    this.uRes = gl.getUniformLocation(program, 'u_res');

    this.rafId = requestAnimationFrame((ts) => this.render(ts));
  }

  ngOnDestroy(): void {
    if (this.rafId != null) cancelAnimationFrame(this.rafId);
    this.rafId = null;
    this.gl = null;
    this.program = null;
  }

  private render(ts: number): void {
    const gl = this.gl;
    const program = this.program;
    const canvas = this.canvasRef.nativeElement;
    if (!gl || !program) return;

    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const w = Math.max(1, Math.floor(canvas.clientWidth * dpr));
    const h = Math.max(1, Math.floor(canvas.clientHeight * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
      gl.viewport(0, 0, w, h);
    }

    gl.useProgram(program);
    gl.uniform1f(this.uTime, ts / 1000);
    gl.uniform2f(this.uRes, canvas.width, canvas.height);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    this.rafId = requestAnimationFrame((t) => this.render(t));
  }

  private createProgram(
    gl: WebGLRenderingContext | WebGL2RenderingContext,
    vsSource: string,
    fsSource: string
  ): WebGLProgram | null {
    const vs = this.compile(gl, gl.VERTEX_SHADER, vsSource);
    const fs = this.compile(gl, gl.FRAGMENT_SHADER, fsSource);
    if (!vs || !fs) return null;
    const program = gl.createProgram();
    if (!program) return null;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
    return program;
  }

  private compile(
    gl: WebGLRenderingContext | WebGL2RenderingContext,
    type: number,
    source: string
  ): WebGLShader | null {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return null;
    return shader;
  }
}
