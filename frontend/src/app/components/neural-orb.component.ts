import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';

@Component({
  selector: 'app-neural-orb',
  template: `<canvas #canvas class="h-full w-full"></canvas>`,
})
export class NeuralOrbComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) private readonly canvasRef!: ElementRef<HTMLCanvasElement>;

  private rafId: number | null = null;
  private pointer = { x: 0, y: 0 };
  private onPointerMove: ((e: PointerEvent) => void) | null = null;
  private gl: WebGLRenderingContext | WebGL2RenderingContext | null = null;
  private program: WebGLProgram | null = null;
  private uTime: WebGLUniformLocation | null = null;
  private uRes: WebGLUniformLocation | null = null;
  private uPtr: WebGLUniformLocation | null = null;

  ngAfterViewInit(): void {
    const canvas = this.canvasRef.nativeElement;
    const gl = (canvas.getContext('webgl2', { antialias: true }) ??
      canvas.getContext('webgl', { antialias: true })) as WebGLRenderingContext | WebGL2RenderingContext | null;
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
      uniform vec2 u_ptr;

      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453123); }
      float noise(vec2 p){
        vec2 i = floor(p), f = fract(p);
        float a = hash(i);
        float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0));
        float d = hash(i + vec2(1.0, 1.0));
        vec2 u = f*f*(3.0-2.0*f);
        return mix(a,b,u.x) + (c-a)*u.y*(1.0-u.x) + (d-b)*u.x*u.y;
      }

      mat2 rot(float a){ float s=sin(a), c=cos(a); return mat2(c,-s,s,c); }

      void main(){
        vec2 frag = gl_FragCoord.xy;
        vec2 uv = (frag - 0.5*u_res) / u_res.y;

        float t = u_time;
        float px = (u_ptr.x*0.5 + 0.5);
        float py = (u_ptr.y*0.5 + 0.5);
        uv *= rot((px-0.5)*0.35);
        uv.y += (py-0.5)*0.18;

        float r = length(uv);
        vec3 col = mix(vec3(0.03,0.06,0.15), vec3(0.06,0.02,0.14), smoothstep(-0.2, 1.2, r));

        float radius = 0.62;
        float inside = smoothstep(radius, radius-0.01, r);
        if(inside > 0.0){
          float z = sqrt(max(0.0, radius*radius - r*r));
          vec3 n = normalize(vec3(uv, z));

          float swirl = noise(n.xy*6.0 + vec2(t*0.25, -t*0.2));
          float bands = abs(sin((n.x*3.0 + n.y*4.0 + swirl*2.0 + t*0.8) * 3.1415));
          float wires = smoothstep(0.85, 1.0, bands);

          vec3 lightDir = normalize(vec3(0.2, 0.4, 1.0));
          float diff = max(0.0, dot(n, lightDir));
          float rim = pow(1.0 - max(0.0, dot(n, vec3(0.0,0.0,1.0))), 2.2);

          vec3 base = vec3(0.15, 0.35, 0.95) * diff + vec3(0.85, 0.2, 0.95) * (0.25 + 0.75*wires);
          col = mix(col, base, inside);
          col += vec3(0.2,0.6,1.0) * (0.35*rim);
          col += vec3(1.0,0.4,0.95) * (0.12*wires);
        }

        float glow = exp(-2.2 * r) * 0.55;
        col += vec3(0.35, 0.7, 1.0) * glow;
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
    this.uPtr = gl.getUniformLocation(program, 'u_ptr');

    const onPointerMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) / Math.max(1, rect.width);
      const y = (e.clientY - rect.top) / Math.max(1, rect.height);
      this.pointer = { x: x * 2 - 1, y: (1 - y) * 2 - 1 };
    };
    this.onPointerMove = onPointerMove;
    canvas.addEventListener('pointermove', onPointerMove);

    this.rafId = requestAnimationFrame((ts) => this.render(ts));
  }

  ngOnDestroy(): void {
    if (this.onPointerMove) {
      this.canvasRef.nativeElement.removeEventListener('pointermove', this.onPointerMove);
      this.onPointerMove = null;
    }
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
    gl.uniform2f(this.uPtr, this.pointer.x, this.pointer.y);
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
