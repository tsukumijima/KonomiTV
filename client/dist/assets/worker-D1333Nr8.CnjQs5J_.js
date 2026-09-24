(function(){"use strict";const M=`#version 300 es
void main() {
  // From the vertex index alone. There is no geometry here worth a buffer.
  vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
`;function S(n,e,t){const i=n.createProgram(),s=z(n,n.VERTEX_SHADER,t),r=z(n,n.FRAGMENT_SHADER,e);if(n.attachShader(i,s),n.attachShader(i,r),n.linkProgram(i),n.deleteShader(s),n.deleteShader(r),!n.getProgramParameter(i,n.LINK_STATUS)){const h=n.getProgramInfoLog(i);throw n.deleteProgram(i),new Error(`the deinterlacer failed to link: ${h??"no reason given"}`)}return i}function z(n,e,t){const i=n.createShader(e);if(!i)throw new Error("the deinterlacer could not create a shader");if(n.shaderSource(i,t),n.compileShader(i),!n.getShaderParameter(i,n.COMPILE_STATUS)){const s=n.getShaderInfoLog(i);throw n.deleteShader(i),new Error(`the deinterlacer failed to compile: ${s??"no reason given"}`)}return i}const ee=`#version 300 es
precision highp float;
uniform sampler2D uTexture;
in vec2 vTextureCoord;
uniform vec3 uTextColor;
uniform vec3 uBackColor;
out vec4 fragColor;

void main() {
  float a = texture(uTexture, vTextureCoord)[3];
  fragColor = vec4(uTextColor * a + uBackColor * (1.0 - a), 1.0);
}
`,te=`#version 300 es
precision highp float;
in vec4 aVertexPosition;
in vec2 aTextureCoord;
uniform mat4 uMatrix;
uniform mat3 uUvMatrix;
out vec2 vTextureCoord;
out vec3 vTextColor;

void main() {
  gl_Position = uMatrix * aVertexPosition;
  vTextureCoord = vec2(uUvMatrix * vec3(aTextureCoord, 1.0));
}
`;function ie(n,e){const t=S(n,ee,te),i=n.getAttribLocation(t,"aVertexPosition"),s=n.getAttribLocation(t,"aTextureCoord"),r=n.getUniformLocation(t,"uTexture"),h=n.getUniformLocation(t,"uMatrix"),o=n.getUniformLocation(t,"uUvMatrix"),l=n.getUniformLocation(t,"uTextColor"),u=n.getUniformLocation(t,"uBackColor");if(r==null||h==null||o==null||l==null||u==null)throw new Error("failed to initialize DEBUG_FRAGMENT_SHADER, DEBUG_VERTEX_SHADER");const a=n.createBuffer(),m=n.createBuffer();return{gl:n,...se(n,e),program:t,programUniforms:{vertex:i,textureCoord:s,texture:r,matrix:h,uvMatrix:o,textColor:l,backColor:u},positionBuffer:a,textureBuffer:m}}function se(n,e){const t=new OffscreenCanvas(0,0),i=t.getContext("2d"),s=new Map;let r=0;const h=0;let o=1;i.font=e,i.fillStyle="white";for(let u=32;u<128;u++){const a=String.fromCharCode(u),m=i.measureText(a),E=Math.ceil(m.actualBoundingBoxDescent+m.actualBoundingBoxAscent+1),f=Math.ceil(m.actualBoundingBoxLeft+m.actualBoundingBoxRight+1);s.set(a,{x:r,y:h,width:f,height:E,metrics:m}),o=Math.max(o,E),r+=f}t.width=r,t.height=o,i.font=e,i.fillStyle="white";for(const[u,a]of s)i.fillText(u,Math.floor(a.x+a.metrics.actualBoundingBoxLeft+1),Math.floor(a.metrics.actualBoundingBoxAscent+1));const l=n.createTexture();return n.bindTexture(n.TEXTURE_2D,l),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MIN_FILTER,n.LINEAR),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MAG_FILTER,n.LINEAR),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_WRAP_S,n.CLAMP_TO_EDGE),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_WRAP_T,n.CLAMP_TO_EDGE),n.texImage2D(n.TEXTURE_2D,0,n.RGBA,n.RGBA,n.UNSIGNED_BYTE,t),{fontTexture:l,chars:s,textureSize:{width:r,height:o}}}function re(n){const e=n.gl;e.deleteBuffer(n.positionBuffer),e.deleteBuffer(n.textureBuffer),e.deleteTexture(n.fontTexture),e.deleteProgram(n.program)}function ne(n,e,t,i,s,r,h){const o=[],l=[],u=t;for(const E of e){if(E===`
`){t=u,i+=h;continue}const f=n.chars.get(E);if(f==null)continue;if(f.width===1){t+=f.metrics.width;continue}const c=Math.floor(t-f.metrics.actualBoundingBoxLeft),p=Math.floor(i-f.metrics.actualBoundingBoxAscent),v=c+f.width,x=p+f.height;o.push(c,p),l.push(f.x,f.y),o.push(c,x),l.push(f.x,f.y+f.height),o.push(c+f.width,x),l.push(f.x+f.width,f.y+f.height),o.push(v,x),l.push(f.x+f.width,f.y+f.height),o.push(c,p),l.push(f.x,f.y),o.push(v,p),l.push(f.x+f.width,f.y),t+=f.metrics.width}const a=n.gl;a.useProgram(n.program),a.bindBuffer(a.ARRAY_BUFFER,n.positionBuffer),a.bufferData(a.ARRAY_BUFFER,new Float32Array(o),a.STATIC_DRAW),a.vertexAttribPointer(n.programUniforms.vertex,2,a.FLOAT,!1,0,0),a.enableVertexAttribArray(n.programUniforms.vertex),a.bindBuffer(a.ARRAY_BUFFER,n.textureBuffer),a.bufferData(a.ARRAY_BUFFER,new Float32Array(l),a.STATIC_DRAW),a.vertexAttribPointer(n.programUniforms.textureCoord,2,a.FLOAT,!1,0,0),a.enableVertexAttribArray(n.programUniforms.textureCoord),a.activeTexture(a.TEXTURE0),a.bindTexture(a.TEXTURE_2D,n.fontTexture),a.uniform1i(n.programUniforms.texture,0),a.uniform3fv(n.programUniforms.textColor,[1,1,1]),a.uniform3fv(n.programUniforms.backColor,[0,0,0]);function m(E,f,c){const p=[];for(let v=0;v<f;v++)for(let x=0;x<E;x++)p.push(c[x*E+v]);return p}a.uniformMatrix4fv(n.programUniforms.matrix,!1,m(4,4,[1/(s/2),0,0,-1,0,-2/r,0,1,0,0,1,0,0,0,0,1])),a.uniformMatrix3fv(n.programUniforms.uvMatrix,!1,m(3,3,[1/n.textureSize.width,0,0,0,1/n.textureSize.height,0,0,0,1])),a.viewport(0,0,s,r),a.enable(a.BLEND),a.blendFunc(a.SRC_ALPHA,a.ONE_MINUS_SRC_ALPHA),a.drawArrays(a.TRIANGLES,0,o.length/2),a.disable(a.BLEND)}const d={firstRepeatsPrevious:0,secondRepeatsNext:1,secondRepeatsPrevious:2,previousSecondRepeated:3,firstRepeatsNext:4,previousFirstRepeated:5,phase:6},F=7,V=2,L=1,he=2,U=10,oe={a:"uA",b:"uB",fieldMetrics:"uFieldMetrics",first:"uFirst",size:"uSize"},X=16,$=8,ae=`#version 300 es

precision highp float;

uniform sampler2D uA;
uniform sampler2D uB;
uniform sampler2D uFieldMetrics;

/** The parity of the field captured first. */
uniform int uFirst;
uniform ivec2 uSize;

layout(location = 0) out vec4 outSecond;
layout(location = 1) out vec4 outFirst;

float luma(vec3 c)
{
  return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

vec4 measure(float diff, float total, float threshold)
{
  diff /= total;
  return vec4(diff, diff > threshold ? 1.0 : 0.0, diff, 1.0);
}

void main()
{
  const int BLOCK_W = ${X};
  const int BLOCK_H = ${$};

  ivec2 block = ivec2(gl_FragCoord.xy);
  ivec2 base = ivec2(block.x * BLOCK_W, block.y * BLOCK_H * 2);

  // Even and odd frame lines, summed apart.
  float diffEven = 0.0;
  float diffOdd = 0.0;
  int totalEven = 0;
  int totalOdd = 0;

  for (int y = 0; y < BLOCK_H; ++y) {
    for (int x = 0; x < BLOCK_W; ++x) {
      ivec2 p = base + ivec2(x, y * 2);

      if (p.x < uSize.x && p.y < uSize.y) {
        float a = luma(texelFetch(uA, p, 0).rgb);
        float b = luma(texelFetch(uB, p, 0).rgb);

        // Ignore small compression artifacts when accumulating differences at moving edges.
        diffEven += max(abs(a - b) - 8.0 / 255.0, 0.0);
        totalEven += 1;
      }
      p.y += 1;
      if (p.x < uSize.x && p.y < uSize.y) {
        float a = luma(texelFetch(uA, p, 0).rgb);
        float b = luma(texelFetch(uB, p, 0).rgb);

        diffOdd += max(abs(a - b) - 8.0 / 255.0, 0.0);
        totalOdd += 1;
      }
    }
  }

  float run = texelFetch(uFieldMetrics, ivec2(${d.phase}, 0), 0)[1];
  float threshold = run == 0.0 ? 0.025 : (run <= 10.0 ? 0.11 : 0.15);

  vec4 even = measure(diffEven, float(totalEven), threshold);
  vec4 odd = measure(diffOdd, float(totalOdd), threshold);
  outFirst = uFirst == 0 ? even : odd;
  outSecond = uFirst == 0 ? odd : even;
}
`,le={second:"uSecond",first:"uFirst",size:"uSize"},k=8,ce=`#version 300 es
precision highp float;

uniform sampler2D uSecond;
uniform sampler2D uFirst;

uniform ivec2 uSize;

layout(location = 0) out vec4 outSecond;
layout(location = 1) out vec4 outFirst;

void main()
{
  ivec2 dst = ivec2(gl_FragCoord.xy);
  ivec2 base = dst * ${k};

  vec4 second = vec4(0.0);
  vec4 first = vec4(0.0);

  for (int y = 0; y < ${k}; ++y) {
    for (int x = 0; x < ${k}; ++x) {
      ivec2 p = base + ivec2(x, y);

      if (p.x < uSize.x && p.y < uSize.y) {
        vec4 value = texelFetch(uSecond, p, 0);
        second[0] = max(second[0], value[0]);
        second.yzw += value.yzw;
        value = texelFetch(uFirst, p, 0);
        first[0] = max(first[0], value[0]);
        first.yzw += value.yzw;
      }
    }
  }

  outSecond = second;
  outFirst = first;
}
`,ue={previous:"uPrevious",second:"uSecond",first:"uFirst",size:"uSize"},fe=`#version 300 es
precision highp float;

uniform sampler2D uPrevious;
uniform sampler2D uSecond;
uniform sampler2D uFirst;

/** The size of the reduced comparisons. */
uniform ivec2 uSize;

out vec4 outValue;

vec4 previous(int metric) {
  return texelFetch(uPrevious, ivec2(metric, 0), 0);
}

/** Fold what REDUCTION left into one texel. */
vec4 fold(sampler2D reduced) {
  vec4 sum = vec4(0.0);
  for (int y = 0; y < uSize.y; ++y) {
    for (int x = 0; x < uSize.x; ++x) {
      vec4 value = texelFetch(reduced, ivec2(x, y), 0);
      sum[0] = max(sum[0], value[0]);
      sum.yzw += value.yzw;
    }
  }
  return vec4(sum[0], sum[1], sum[2] / max(sum[3], 1.0), sum[3]);
}

bool same(float differing) {
  return differing <= ${V}.0;
}

// A repeated field changes less than the opposite field.
// Distinguish motion shared by both fields from a still image with small absolute differences.
bool repeats(vec4 field, vec4 other) {
  return same(field[1]) &&
    (max(field[0], other[0]) < 0.025 || field[2] < other[2] * 0.75);
}

/** The phase texel, (phase, run), from the six comparisons' differing counts. */
vec4 decide(vec4 last, vec4 dFirstRepeatsPrevious, vec4 dSecondRepeatsNext,
            vec4 dSecondRepeatsPrevious, vec4 dPreviousSecondRepeated,
            vec4 dFirstRepeatsNext, vec4 dPreviousFirstRepeated)
{
  bool firstRepeatsPrevious = repeats(dFirstRepeatsPrevious, dSecondRepeatsPrevious);
  bool secondRepeatsNext = repeats(dSecondRepeatsNext, dFirstRepeatsNext);
  bool secondRepeatsPrevious = repeats(dSecondRepeatsPrevious, dFirstRepeatsPrevious);
  bool previousSecondRepeated = repeats(dPreviousSecondRepeated, dPreviousFirstRepeated);
  bool firstRepeatsNext = repeats(dFirstRepeatsNext, dSecondRepeatsNext);
  bool previousFirstRepeated = repeats(dPreviousFirstRepeated, dPreviousSecondRepeated);
  bool still = (firstRepeatsPrevious && secondRepeatsPrevious) || (secondRepeatsNext && firstRepeatsNext);

  int previous = int(last[0]);
  float run = last[1];
  // What each phase looks like: one field repeats, the other plainly does not.
  bool looks1 = firstRepeatsPrevious && !secondRepeatsPrevious;
  bool looks2 = secondRepeatsNext && !firstRepeatsNext;
  bool looks3 = secondRepeatsPrevious && !firstRepeatsPrevious;
  bool looks4 = previousSecondRepeated && !previousFirstRepeated;
  bool looks5 = firstRepeatsNext && !secondRepeatsNext;

  int expected = previous == 0 ? 0 : (previous == 5 ? 1 : previous + 1);
  bool expectedRepeat =
    expected == 1 ? firstRepeatsPrevious :
    expected == 2 ? secondRepeatsNext :
    expected == 3 ? secondRepeatsPrevious :
    expected == 4 ? previousSecondRepeated :
    expected == 5 ? firstRepeatsNext : false;
  bool expectedLooks =
    expected == 1 ? looks1 :
    expected == 2 ? looks2 :
    expected == 3 ? looks3 :
    expected == 4 ? looks4 :
    expected == 5 ? looks5 : false;
  bool believed = run >= ${U}.0;
  bool carried = believed ? expectedRepeat : expectedLooks;

  int phase = 0;
  if (expected != 0 && carried) {
    phase = expected;
    run += 1.0;
  } else if (expected != 0 && (still || expectedRepeat)) {
    // Uninformative: keeps the cycle's place, counts only once believed.
    phase = expected;
    if (believed) run += 1.0;
  } else if (looks1) {
    phase = 1;
  } else if (looks2) {
    phase = 2;
  } else if (looks3) {
    phase = 3;
  } else if (looks4) {
    phase = 4;
  } else if (looks5) {
    phase = 5;
  }
  if (phase != expected) run = phase != 0 ? 1.0 : 0.0;
  return vec4(float(phase), run, 0.0, 0.0);
}

void main()
{
  int metric = int(gl_FragCoord.x);
  // The comparisons against the next frame become, a frame later, the ones
  // against the previous frame, and those the ones before.
  if (metric == ${d.firstRepeatsPrevious}) {
    outValue = previous(${d.firstRepeatsNext});
  } else if (metric == ${d.secondRepeatsNext}) {
    outValue = fold(uSecond);
  } else if (metric == ${d.secondRepeatsPrevious}) {
    outValue = previous(${d.secondRepeatsNext});
  } else if (metric == ${d.previousSecondRepeated}) {
    outValue = previous(${d.secondRepeatsPrevious});
  } else if (metric == ${d.firstRepeatsNext}) {
    outValue = fold(uFirst);
  } else if (metric == ${d.previousFirstRepeated}) {
    outValue = previous(${d.firstRepeatsPrevious});
  } else {
    outValue = decide(
      previous(${d.phase}),
      previous(${d.firstRepeatsNext}),
      fold(uSecond),
      previous(${d.secondRepeatsNext}),
      previous(${d.secondRepeatsPrevious}),
      fold(uFirst),
      previous(${d.firstRepeatsPrevious})
    );
  }
}
`,de={prev:"uPrev",cur:"uCur",next:"uNext",size:"uSize",parity:"uParity",tff:"uTff",spatialCheck:"uSpatialCheck",debug:"uDebug",film:"uFilm",second:"uSecond",phase:"uPhase",fieldMetrics:"uFieldMetrics"},me=`#version 300 es
precision highp float;
precision highp int;

uniform sampler2D uPrev;
uniform sampler2D uCur;
uniform sampler2D uNext;
uniform sampler2D uFieldMetrics;
/** The size of a frame in texels. */
uniform ivec2 uSize;
/** The parity of the lines that are kept; the others are interpolated. */
uniform int uParity;
/** Whether the first field of a frame is its top field. */
uniform int uTff;
/** Whether the temporal bound is widened by the local vertical range. */
uniform bool uSpatialCheck;
uniform bool uDebug;
uniform bool uFilm;
uniform bool uSecond;
uniform int uPhase;

out vec4 fragColor;

/**
 * A texel, with the edges of the frame mirrored.
 *
 * The reference reflects its line offsets on the first and last line rather
 * than reading outside the frame, and this is the same thing said once.
 */
vec3 fetch(sampler2D image, int x, int y) {
  int line = y < 0 ? -y : (y >= uSize.y ? 2 * (uSize.y - 1) - y : y);
  return texelFetch(image, ivec2(clamp(x, 0, uSize.x - 1), clamp(line, 0, uSize.y - 1)), 0).rgb;
}

/**
 * Interpolate the missing line along whichever direction the picture runs in.
 *
 * a..g are the seven texels of the line above and h..n those of the line
 * below, both centred on the pixel being built. The straight vertical average
 * is the starting point, and each candidate direction is taken only if the
 * three differences across it are smaller than the best so far; the steeper
 * pair of directions is only considered when the shallower one was an
 * improvement, which is what keeps a busy picture from finding an edge that is
 * not there.
 */
vec3 spatialPredictor(vec3 a, vec3 b, vec3 c, vec3 d, vec3 e, vec3 f, vec3 g,
                      vec3 h, vec3 i, vec3 j, vec3 k, vec3 l, vec3 m, vec3 n) {
  vec3 pred = (d + k) * 0.5;
  vec3 best = abs(c - j) + abs(d - k) + abs(e - l);

  vec3 score = abs(b - k) + abs(c - l) + abs(d - m);
  vec3 taken = vec3(lessThan(score, best));
  pred = mix(pred, (c + l) * 0.5, taken);
  best = mix(best, score, taken);

  score = abs(a - l) + abs(b - m) + abs(c - n);
  taken *= vec3(lessThan(score, best));
  pred = mix(pred, (b + m) * 0.5, taken);
  best = mix(best, score, taken);

  score = abs(d - i) + abs(e - j) + abs(f - k);
  taken = vec3(lessThan(score, best));
  pred = mix(pred, (e + j) * 0.5, taken);
  best = mix(best, score, taken);

  score = abs(e - h) + abs(f - i) + abs(g - j);
  taken *= vec3(lessThan(score, best));
  pred = mix(pred, (f + i) * 0.5, taken);

  return pred;
}

/**
 * Hold the spatial guess to what the moving picture allows.
 *
 * p2 is where the line would be if nothing moved -- the average of the same
 * line in the two frames that bracket this moment -- and the three temporal
 * differences say how much did move. The spatial guess is then clamped to that
 * distance from p2: still picture, and the answer is the line that is really
 * there; motion, and the interpolation is free to take over.
 */
vec3 temporalPredictor(vec3 A, vec3 B, vec3 C, vec3 D, vec3 E, vec3 F,
                       vec3 G, vec3 H, vec3 I, vec3 J, vec3 K, vec3 L,
                       vec3 spatialPred, bool skipCheck) {
  vec3 p0 = (C + H) * 0.5;
  vec3 p1 = F;
  vec3 p2 = (D + I) * 0.5;
  vec3 p3 = G;
  vec3 p4 = (E + J) * 0.5;

  vec3 tdiff0 = abs(D - I) * 0.5;
  vec3 tdiff1 = (abs(A - F) + abs(B - G)) * 0.5;
  vec3 tdiff2 = (abs(K - F) + abs(G - L)) * 0.5;

  vec3 diff = max(tdiff0, max(tdiff1, tdiff2));

  if (!skipCheck) {
    vec3 hi = max(p2 - p3, max(p2 - p1, min(p0 - p1, p4 - p3)));
    vec3 lo = min(p2 - p3, min(p2 - p1, max(p0 - p1, p4 - p3)));
    diff = max(diff, max(lo, -hi));
  }

  return clamp(spatialPred, p2 - diff, p2 + diff);
}

/**
 * Build one interpolated pixel.
 *
 * prev2 and next2 are the frames the missing line is bracketed by, which is
 * not the same pair as prev and next: the field being rebuilt is half a frame
 * from one of its neighbours and one and a half from the other, and it is the
 * near pair that says what the picture looked like around this moment. prev
 * and next themselves are still read, for the two motion measurements.
 */
vec3 filterPixel(sampler2D prev2, sampler2D next2, int x, int y) {
  vec3 a = fetch(uCur, x - 3, y - 1);
  vec3 b = fetch(uCur, x - 2, y - 1);
  vec3 c = fetch(uCur, x - 1, y - 1);
  vec3 d = fetch(uCur, x, y - 1);
  vec3 e = fetch(uCur, x + 1, y - 1);
  vec3 f = fetch(uCur, x + 2, y - 1);
  vec3 g = fetch(uCur, x + 3, y - 1);

  vec3 h = fetch(uCur, x - 3, y + 1);
  vec3 i = fetch(uCur, x - 2, y + 1);
  vec3 j = fetch(uCur, x - 1, y + 1);
  vec3 k = fetch(uCur, x, y + 1);
  vec3 l = fetch(uCur, x + 1, y + 1);
  vec3 m = fetch(uCur, x + 2, y + 1);
  vec3 n = fetch(uCur, x + 3, y + 1);

  // Within three texels of either side there is no room to look along an edge,
  // so the reference takes the vertical average there and so does this.
  bool interior = x >= 3 && x + 3 < uSize.x;
  vec3 spatialPred = interior ? spatialPredictor(a, b, c, d, e, f, g, h, i, j, k, l, m, n)
                              : (d + k) * 0.5;

  vec3 A = fetch(uPrev, x, y - 1);
  vec3 B = fetch(uPrev, x, y + 1);
  vec3 C = fetch(prev2, x, y - 2);
  vec3 D = fetch(prev2, x, y);
  vec3 E = fetch(prev2, x, y + 2);
  vec3 F = d;
  vec3 G = k;
  vec3 H = fetch(next2, x, y - 2);
  vec3 I = fetch(next2, x, y);
  vec3 J = fetch(next2, x, y + 2);
  vec3 K = fetch(uNext, x, y - 1);
  vec3 L = fetch(uNext, x, y + 1);

  // The first and last line the filter builds have only one line of picture
  // outside them, so the range the spatial check would be measured over is not
  // there. The reference drops the check on those two lines.
  bool skipCheck = !uSpatialCheck || y < 2 || y + 2 >= uSize.y;
  return temporalPredictor(A, B, C, D, E, F, G, H, I, J, K, L, spatialPred, skipCheck);
}

int firstParity() {
  return uTff != 0 ? 0 : 1;
}

bool same(int metric) {
  return texelFetch(uFieldMetrics, ivec2(metric, 0), 0)[1] <= ${V}.0;
}

/** The pulldown phase the detection gave this frame, or 0. See film-shader.ts. */
int detectedPhase() {
  vec4 phase = texelFetch(uFieldMetrics, ivec2(${d.phase}, 0), 0);
  // Deinterlace each field normally until the cadence is confirmed.
  return phase[1] >= ${U}.0 ? int(phase[0]) : 0;
}

bool isMixedPhase(int phase) {
  return phase == ${L} || phase == ${he};
}

/** Detect new combing in phase 4, whose cadence is inferred from previous repeats. */
bool movingComb(vec3 pixel, int x, int y) {
  vec3 above = fetch(uCur, x, y - 1);
  vec3 below = fetch(uCur, x, y + 1);
  vec3 comb = max(min(above, below) - pixel, pixel - max(above, below));
  // Phase 3 is a complete film frame, so use its vertical detail as the reference.
  // Preserve existing horizontal lines and interpolate only pixels with new combing.
  vec3 previous = fetch(uPrev, x, y);
  vec3 previousAbove = fetch(uPrev, x, y - 1);
  vec3 previousBelow = fetch(uPrev, x, y + 1);
  vec3 previousComb = max(min(previousAbove, previousBelow) - previous,
                          previous - max(previousAbove, previousBelow));
  return any(greaterThan(comb, max(previousComb, vec3(0.0)) + vec3(8.0 / 255.0)));
}

const int DEBUG_BAR_CELL = 32;
const int DEBUG_BAR_WIDTH = DEBUG_BAR_CELL * 7;
const int DEBUG_BAR_HEIGHT = 16;

vec3 debugBar(int x) {
  int cell = x / DEBUG_BAR_CELL;
  bool lit = x % DEBUG_BAR_CELL >= DEBUG_BAR_CELL - 4;
  if (cell == 6) return lit || uSecond ? vec3(1.0, 0.0, 0.0) : vec3(0.0);
  return lit || same(cell) ? vec3(1.0) : vec3(0.0);
}

const int DIGIT_WIDTH = 24;
const int DIGIT_HEIGHT = 60;

bool digitLit(int digit, int x, int y) {
  bool a = y < 20;
  bool b = x >= 20 && y < 40;
  bool c = x >= 20 && y >= 40;
  bool d = y >= 56;
  bool e = x < 4 && y >= 40;
  bool f = x < 4 && y < 40;
  bool g = y >= 36 && y < 40;
  switch (digit) {
    case 1: return b || c;
    case 2: return a || b || d || e || g;
    case 3: return a || b || c || d || g;
    case 4: return b || c || f || g;
    case 5: return a || c || d || f || g;
    default: return false;
  }
}

void main() {
  ivec2 at = ivec2(gl_FragCoord.xy);
  int x = at.x;
  // The framebuffer counts its rows from the bottom and a frame from the top.
  int y = uSize.y - 1 - at.y;

  vec3 rgb;
  if (uFilm && uDebug && y < DEBUG_BAR_HEIGHT && x < DEBUG_BAR_WIDTH) {
    rgb = debugBar(x);
  } else if (uFilm && uDebug && x < DIGIT_WIDTH && y < DIGIT_HEIGHT && uPhase > 0) {
    rgb = digitLit(uPhase, x, y) ? vec3(1.0, 0.0, 0.0) : vec3(0.0);
  } else if (uFilm && !uSecond && detectedPhase() != 0) {
    bool mixed = isMixedPhase(detectedPhase());
    rgb = mixed && (y & 1) != firstParity()
      ? texelFetch(uPrev, ivec2(x, y), 0).rgb
      : texelFetch(uCur, ivec2(x, y), 0).rgb;
    if (detectedPhase() == 4 && (y & 1) != uParity && movingComb(rgb, x, y))
      rgb = filterPixel(uPrev, uCur, x, y);
  } else if ((y & 1) == uParity) {
    rgb = texelFetch(uCur, ivec2(x, y), 0).rgb;
  } else if ((uParity ^ uTff) != 0) {
    // The first field of the frame: the moment it holds sits between the
    // previous frame and the second field of this one.
    rgb = filterPixel(uPrev, uCur, x, y);
  } else {
    rgb = filterPixel(uCur, uNext, x, y);
  }
  fragColor = vec4(rgb, 1.0);
}
`,R={phase:0,run:0};function I(n,e,t){return Object.fromEntries(Object.entries(t).map(([i,s])=>[i,n.getUniformLocation(e,s)]))}class H{#t;#r;#e;#h;#i;#s;#d;#u=null;#v=null;#m=null;#b=0;#o=null;#l=null;#E=0;#a=0;metrics=new Float32Array(F*4);#n=0;#c=0;constructor(e){this.#t=e,this.#r=S(e,ae,M),this.#e=I(e,this.#r,oe),this.#h=S(e,ce,M),this.#i=I(e,this.#h,le),this.#s=S(e,fe,M),this.#d=I(e,this.#s,ue)}get texture(){return this.#m?.[this.#b]?.textures[0]??null}resize(e,t){e===this.#n&&t===this.#c||(this.#n=e,this.#c=t,this.#w())}reset(){const e=this.#t;e.deleteSync(this.#l),this.#l=null,this.#E=0;const t=this.#m?.[this.#b];if(!t)return;const i=new Float32Array(F*4);for(let s=0;s<d.phase;s++)i[s*4+1]=1;e.bindTexture(e.TEXTURE_2D,t.textures[0]??null),e.texSubImage2D(e.TEXTURE_2D,0,0,0,F,1,e.RGBA,e.FLOAT,i)}detect(e,t,i){const s=this.#t;if(this.#n===0||this.#c===0)return;this.#S();const r=this.#u,h=this.#v,o=this.#m;if(r===null||h===null||o===null)return;const l=o[this.#b],u=o[1-this.#b];if(s.bindFramebuffer(s.FRAMEBUFFER,r.framebuffer),s.useProgram(this.#r),this.#x(0,e,this.#e.a),this.#x(1,t,this.#e.b),this.#x(2,l.textures[0],this.#e.fieldMetrics),s.uniform1i(this.#e.first,i),s.uniform2i(this.#e.size,this.#n,this.#c),s.viewport(0,0,r.width,r.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,h.framebuffer),s.useProgram(this.#h),this.#x(0,r.textures[0],this.#i.second),this.#x(1,r.textures[1],this.#i.first),s.uniform2i(this.#i.size,r.width,r.height),s.viewport(0,0,h.width,h.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,u.framebuffer),s.useProgram(this.#s),this.#x(0,l.textures[0],this.#d.previous),this.#x(1,h.textures[0],this.#d.second),this.#x(2,h.textures[1],this.#d.first),s.uniform2i(this.#d.size,h.width,h.height),s.viewport(0,0,F,1),s.drawArrays(s.TRIANGLES,0,3),this.#b=1-this.#b,this.#E++,this.#l!==null){s.bindFramebuffer(s.FRAMEBUFFER,null);return}this.#a=this.#E,s.bindBuffer(s.PIXEL_PACK_BUFFER,this.#o),s.readPixels(0,0,F,1,s.RGBA,s.FLOAT,0),s.bindBuffer(s.PIXEL_PACK_BUFFER,null),s.bindFramebuffer(s.FRAMEBUFFER,null),this.#l=s.fenceSync(s.SYNC_GPU_COMMANDS_COMPLETE,0),s.flush()}poll(){const e=this.#t,t=this.#l;if(t===null||this.#o===null)return null;switch(e.clientWaitSync(t,0,0)){case e.ALREADY_SIGNALED:case e.CONDITION_SATISFIED:return e.bindBuffer(e.PIXEL_PACK_BUFFER,this.#o),e.getBufferSubData(e.PIXEL_PACK_BUFFER,0,this.metrics),e.bindBuffer(e.PIXEL_PACK_BUFFER,null),e.deleteSync(t),this.#l=null,{phase:this.metrics[d.phase*4]??0,run:this.metrics[d.phase*4+1]??0,age:this.#E-this.#a};default:return null}}destroy(){const e=this.#t;if(this.#w(),this.#m!==null){for(const t of this.#m)P(e,t);this.#m=null}e.deleteSync(this.#l),this.#l=null,e.deleteBuffer(this.#o),this.#o=null,e.deleteProgram(this.#r),e.deleteProgram(this.#h),e.deleteProgram(this.#s)}#x(e,t,i){const s=this.#t;s.activeTexture(s.TEXTURE0+e),s.bindTexture(s.TEXTURE_2D,t??null),s.uniform1i(i,e)}#w(){const e=this.#t;this.#u!==null&&P(e,this.#u),this.#v!==null&&P(e,this.#v),this.#u=null,this.#v=null}#S(){const e=this.#t;if(this.#u===null||this.#v===null){this.#w();const t=Math.ceil(this.#n/X),i=Math.ceil(this.#c/($*2));this.#u=D(e,t,i,2),this.#v=D(e,Math.ceil(t/k),Math.ceil(i/k),2)}this.#m===null&&(this.#m=[D(e,F,1,1),D(e,F,1,1)],this.#b=0,this.reset()),this.#o===null&&(this.#o=e.createBuffer(),e.bindBuffer(e.PIXEL_PACK_BUFFER,this.#o),e.bufferData(e.PIXEL_PACK_BUFFER,this.metrics.byteLength,e.STREAM_COPY),e.bindBuffer(e.PIXEL_PACK_BUFFER,null))}}function D(n,e,t,i){const s=n.createFramebuffer();n.bindFramebuffer(n.FRAMEBUFFER,s);const r=[];for(let l=0;l<i;l++){const u=n.createTexture();n.bindTexture(n.TEXTURE_2D,u),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MIN_FILTER,n.NEAREST),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MAG_FILTER,n.NEAREST),n.texImage2D(n.TEXTURE_2D,0,n.RGBA32F,e,t,0,n.RGBA,n.FLOAT,null),n.framebufferTexture2D(n.FRAMEBUFFER,n.COLOR_ATTACHMENT0+l,n.TEXTURE_2D,u,0),r.push(u)}n.drawBuffers(r.map((l,u)=>n.COLOR_ATTACHMENT0+u));const h=n.checkFramebufferStatus(n.FRAMEBUFFER)===n.FRAMEBUFFER_COMPLETE;n.bindFramebuffer(n.FRAMEBUFFER,null);const o={framebuffer:s,textures:r,width:e,height:t};if(!h)throw P(n,o),new Error("failed to allocate framebuffer");return o}function P(n,{framebuffer:e,textures:t}){n.deleteFramebuffer(e);for(const i of t)n.deleteTexture(i)}function _(n,e=0,t=n.length){const i=new DataView(n.buffer,n.byteOffset,n.byteLength),s=[];for(let r=e;r<t;){if(r+8>t)throw new Error("Incomplete MP4 box");const h=i.getUint32(r);if(h<8||r+h>t)throw new Error("Invalid MP4 box size");s.push({type:String.fromCharCode(...n.subarray(r+4,r+8)),start:r,body:r+8,end:r+h}),r+=h}return s}function pe(n,e){for(const t of _(n,e.body,e.end).filter(i=>i.type==="trak")){let i=t;for(const s of["mdia","minf","stbl","stsd"]){const r=_(n,i.body,i.end).find(h=>h.type===s);if(!r)break;i=r}if(i.type==="stsd")for(const s of _(n,i.body+8,i.end)){if(s.type!=="avc1")continue;const r=_(n,s.body+78,s.end).find(l=>l.type==="avcC");if(!r)throw new Error("AVC sample entry has no avcC");const h=n.slice(r.body,r.end);return{codec:"avc1."+Array.from(h.subarray(1,4)).map(l=>l.toString(16).padStart(2,"0")).join(""),description:h}}}return null}class ve{#t;#r=null;#e=null;#h=[];#i=0;#s=null;#d=[];#u=new Set;#v=!1;#m=!1;#b=!1;#o=!1;#l=!1;#E=new WeakMap;constructor(e){this.#t=e,e.addEventListener("seeking",this.#n),e.addEventListener("ratechange",this.#n)}get active(){return this.#o}append(e){if(this.#b)return;const t=new Uint8Array(e),i=new DataView(e);try{for(const r of _(t)){if(r.type==="moov"){this.#r=pe(t,r);const h=this.#r;h&&VideoDecoder.isConfigSupported(h).then(o=>{this.#E.set(h,o.supported===!0)}).catch(o=>this.#c(o))}if(!(r.type!=="moof"||this.#r===null))for(const h of _(t,r.body,r.end).filter(o=>o.type==="traf")){const o=_(t,h.body,h.end),l=o.find(c=>c.type==="tfhd");if(!l||i.getUint32(l.body+4)!==1)continue;const u=o.find(c=>c.type==="tfdt"),a=o.find(c=>c.type==="trun");if(!u||!a||i.getUint32(u.body)!==16777216||i.getUint32(a.body)!==16781057)throw new Error("Unexpected mpeg2toh264 video fragment layout");let m=Number(i.getBigUint64(u.body+4)),E=r.start+i.getInt32(a.body+8);const f=i.getUint32(a.body+4);if(a.body+12+f*16>a.end)throw new Error("Incomplete video samples");for(let c=0;c<f;c++){const p=a.body+12+c*16,v=i.getUint32(p),x=i.getUint32(p+4),G=i.getUint32(p+8),Xe=i.getInt32(p+12);if(E<0||E+x>t.length)throw new Error("Video sample outside fragment");this.#h.push({config:this.#r,decodeTime:m/9e4,timestamp:Math.round((m+Xe)*1e6/9e4),duration:Math.round(v*1e6/9e4),type:G&65536?"delta":"key",data:t.subarray(E,E+x)}),m+=v,E+=x}}}const s=this.#t.buffered;if(s.length>0){let r=0;for(let h=0;h<(this.#o?this.#i:this.#h.length);h++){const o=this.#h[h];o.type==="key"&&o.timestamp/1e6<=s.start(0)&&(r=h)}r>0&&(this.#h.splice(0,r),this.#i=Math.max(0,this.#i-r))}}catch(s){this.#c(s)}}take(){if(this.#b||this.#t.playbackRate<=1.25||this.#r===null||this.#E.get(this.#r)!==!0){this.#o&&this.#n();return}this.#o||(this.#n(),this.#o=!0);const e=this.#t.currentTime;try{for(;this.#i<this.#h.length&&(this.#s?.decodeQueueSize??0)<6&&this.#d.length<12;){const i=this.#h[this.#i];if(i.decodeTime>e+.25)break;if(this.#e!==i.config){if(this.#s){if(!this.#m){this.#m=!0;const r=this.#s;r.flush().then(()=>{this.#s===r&&(r.close(),this.#s=null,this.#e=null,this.#m=!1)}).catch(h=>{this.#s===r&&this.#c(h)})}break}const s=new VideoDecoder({output:r=>{this.#s!==s?r.close():this.#a(r)},error:r=>{this.#s===s&&this.#c(r)}});this.#s=s,this.#s.configure(i.config),this.#e=i.config}(i.duration??0)<1e3&&this.#u.add(i.timestamp),this.#s.decode(new EncodedVideoChunk(i)),this.#i++}if(this.#v&&this.#i===this.#h.length&&this.#s&&!this.#m){this.#m=!0;const i=this.#s;i.flush().catch(s=>{this.#s===i&&this.#c(s)})}}catch(i){this.#c(i);return}const t=this.#d[0];return!t||t.timestamp/1e6>e+.003*this.#t.playbackRate?this.#l?null:void 0:(this.#l=!0,this.#d.shift())}#a=e=>{this.#u.delete(e.timestamp)||e.timestamp/1e6<this.#t.currentTime-(this.#l?.1:.04)?e.close():this.#d.push(e)};#n=()=>{this.#s&&this.#s.state!=="closed"&&this.#s.close(),this.#s=null,this.#e=null;for(const e of this.#d)e.close();this.#d=[],this.#u.clear(),this.#m=!1,this.#o=!1,this.#l=!1,this.#i=0;for(let e=0;e<this.#h.length;e++){const t=this.#h[e];t.type==="key"&&t.timestamp/1e6<=this.#t.currentTime&&(this.#i=e)}};finish(){this.#v=!0}suspend(){this.#n()}reset(){this.#n(),this.#h=[],this.#i=0,this.#r=null,this.#v=!1,this.#b=!1}destroy(){this.reset(),this.#t.removeEventListener("seeking",this.#n),this.#t.removeEventListener("ratechange",this.#n)}#c(e){this.#n(),this.#b=!0,console.warn("mpeg2toh264: decoded video input unavailable",e)}}const W=["mozParsedFrames","mozDecodedFrames","mozPresentedFrames","mozPaintedFrames"];function Ee(n){return W.every(e=>e in n)}function xe(n){return n.ownerDocument?.defaultView?.performance.timeOrigin??performance.timeOrigin}const ge=250,be=500;class Te{#t;#r;#e;#h=null;#i=null;#s=null;#d=null;#u=!1;#v=!0;#m=null;#b=null;#o=0;#l;#E;#a=null;#n=null;#c=null;#x=null;#w=0;#S=[];#R=[];constructor(e,t){if(this.#t=e,this.#r=t,this.#e=Ee(e)?e:null,this.#l=this.#e===null&&typeof VideoFrame<"u",this.#E=this.#l&&e.playbackRate>1,this.#e){for(const i of["emptied","seeking","seeked"])e.addEventListener(i,this.#I);for(const i of["pause","playing","waiting","ratechange"])e.addEventListener(i,this.#_)}if(this.#l)for(const i of["loadeddata","playing","pause","ended","seeking","seeked","emptied","ratechange"])e.addEventListener(i,this.#xe)}get mozDriven(){return this.#e!==null&&!this.#E}get captureDriven(){return this.#E}get hasDelivered(){return this.#u}request(e){if(this.#i===null){if(this.#i=e,this.#E){this.#U();return}this.#h=this.#e?requestAnimationFrame(this.#O):this.#t.requestVideoFrameCallback(this.#ge)}}cancel(){this.#h!==null&&(this.#e?cancelAnimationFrame(this.#h):this.#t.cancelVideoFrameCallback(this.#h)),this.#h=null,this.#i=null,this.#a?.(),this.#a=null,this.#c!==null&&this.#t.cancelVideoFrameCallback(this.#c),this.#c=null,this.#H(),this.#x=null,this.#S=[],this.#I()}destroy(){this.cancel();for(const e of["emptied","seeking","seeked"])this.#t.removeEventListener(e,this.#I);for(const e of["pause","playing","waiting","ratechange"])this.#t.removeEventListener(e,this.#_);for(const e of["loadeddata","playing","pause","ended","seeking","seeked","emptied","ratechange"])this.#t.removeEventListener(e,this.#xe)}flush(e){if(this.#E)for(this.#t.ownerDocument!==this.#n&&(this.#a?.(),this.#a=null,this.#U());this.#R.length>0&&this.#i!==null;){const t=this.#R.shift(),i=t.frame;try{this.#D(e,{width:i.visibleRect?.width??i.codedWidth,height:i.visibleRect?.height??i.codedHeight,mediaTime:i.timestamp/1e6,presentedFrames:t.count,expectedDisplayTime:t.at,timeOrigin:performance.timeOrigin,frame:i})}finally{i.close()}}}#H(){for(const e of this.#R)e.frame.close();this.#R=[]}#xe=e=>{const t=this.#l&&this.#t.playbackRate>1;if(t!==this.#E){const i=this.#i;this.cancel(),this.#E=t,i!==null&&this.request(i);return}this.#E&&((e.type==="pause"||e.type==="ended")&&this.flush(performance.now()),this.#H(),["seeking","seeked","emptied","ratechange"].includes(e.type)&&(this.#x=null,this.#S=[]),this.#a?.(),this.#a=null,this.#i!==null&&this.#U())};#U(){if(this.#a!==null||this.#i===null||(this.#t.paused||this.#t.ended)&&this.#x!==null)return;this.#c===null&&typeof this.#t.requestVideoFrameCallback=="function"&&(this.#c=this.#t.requestVideoFrameCallback(this.#te));const e=Math.max(4,8/Math.max(1,this.#t.playbackRate)),t=this.#t.ownerDocument?.defaultView;if(this.#n=this.#t.ownerDocument,t){const i=t.setTimeout(this.#B,e);this.#a=()=>t.clearTimeout(i)}else{const i=setTimeout(this.#B,e);this.#a=()=>clearTimeout(i)}}#te=()=>{this.#c=null,this.#a?.(),this.#a=null,this.#B()};#B=()=>{this.#a=null;const e=this.#t;if(this.#i===null)return;if(e.readyState<2||e.seeking){this.#U();return}let t,i=!1;try{const s=this.#r?.();if(s===null){this.#U();return}i=s!==void 0,t=s??new VideoFrame(e)}catch(s){if(!(s instanceof DOMException)||s.name!=="InvalidStateError")throw s;this.#U();return}if(t.timestamp===this.#x)t.close();else{let s=1;if(this.#x!==null){const h=t.timestamp-this.#x;if(h>1e3&&h<25e4){this.#S.push(h),this.#S.length>7&&this.#S.shift();const o=[...this.#S].sort((u,a)=>u-a),l=o[Math.floor(o.length/2)];s=Math.max(1,Math.round(h/l))}}this.#x=t.timestamp,this.#w+=s;const r=performance.now()+(i?(t.timestamp/1e6-e.currentTime)*1e3/e.playbackRate:0);for(this.#R.push({frame:t,at:r,count:this.#w});this.#R.length>4;)this.#R.shift().frame.close()}this.#U()};#_=()=>{this.#m=null,this.#b=null,this.#o=0};#I=()=>{this.#s=null,this.#d=null,this.#v=!0,this.#_()};#ge=(e,t)=>{this.#D(e,{width:t.width,height:t.height,mediaTime:t.mediaTime,presentedFrames:t.presentedFrames,expectedDisplayTime:t.expectedDisplayTime,timeOrigin:xe(this.#t)})};#D=(e,t)=>{const i=this.#i;this.#h=null,this.#i=null,this.#u=!0,i?.(e,t)};#O=e=>{const t=this.#e,i=W.map(o=>t[o]);this.#s?.some((o,l)=>i[l]<o)&&this.#I(),this.#s=i;const s=t.mozPaintedFrames,r=!t.seeking&&t.readyState>=2&&t.videoWidth>0&&t.videoHeight>0,h=this.#d===null&&(s>0||t.paused&&(t.mozPresentedFrames>0||t.mozDecodedFrames>0));if(r&&(h||this.#d!==null&&s!==this.#d)){if(this.#m!==null&&e-this.#m>be&&(this.#_(),this.#v=!0),!t.paused&&!t.ended){const l=this.#b;if(l&&e-l.at>=ge){const u=s-l.frames;if(u>0){const a=(e-l.at)/u;a>=4&&a<=200&&(this.#o=this.#o?this.#o+(a-this.#o)*.25:a)}this.#b=null}this.#b??={at:e,frames:s}}this.#m=e,this.#d=s;const o=this.#v;this.#v=!1,this.#D(e,{width:t.videoWidth,height:t.videoHeight,mediaTime:t.currentTime,presentedFrames:s,expectedDisplayTime:e,timeOrigin:performance.timeOrigin,mozTiming:{periodMs:this.#o,discontinuity:o}})}else this.#h=requestAnimationFrame(this.#O)}}let ye=null;const q=.5,T=4,B=5,A=B+1,K=1e3,N=4,C=200,Fe=.25,Re=1e3/60,_e=250,Ae=1e3/30,we=`#version 300 es
void main() {
  // One triangle over the whole viewport, from the vertex index alone. There
  // is no geometry here worth a buffer: every pixel is the fragment shader's.
  vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
`,ke=.75,Se=.1,Q=1,De=.02,Pe=.1,j=1,Ce=4,O=5,Me=4,Le={2:0,3:.25,4:.5,5:.75},Ue=`#version 300 es
precision highp float;
uniform sampler2D uField;
uniform bool uFlip;
out vec4 fragColor;
void main() {
  ivec2 position = ivec2(gl_FragCoord.xy);
  if (uFlip) position.y = textureSize(uField, 0).y - 1 - position.y;
  fragColor = texelFetch(uField, position, 0);
}
`,Ie={requestAnimationFrame:n=>requestAnimationFrame(n),cancelAnimationFrame:n=>cancelAnimationFrame(n)};class Be extends EventTarget{encodedVideo;#t;#r;#e;#h;#i;#s=null;#d;#u;#v;#m;#b;#o=[];#l=[];#E=A-1;#a=null;#n=[];#c=null;#x=0;#w=null;#S=null;#R=Re;#H=0;#xe=0;#U=0;#te=0;#B=null;#_(){this.#n.length=0,this.#B=null,this.#te=0}#I=null;#ge;#D;#O;#ie=0;#G;#k;#g=0;#M=0;#z=0;#L=T-1;#y=0;#be=0;#Qe=0;#Ue=Number.NaN;#Te=!1;#Ie=0;#se=0;#je=0;#F=!1;#Y=0;#Be=!1;#V=!1;#T=null;#re=[];#N=!1;#Ye;#Je;#A;#ne;#W;#Ze;#f=null;#p;#ye=!1;#et=0;#tt=!1;#Ht=0;#Fe=!1;#Ne=!1;#he=null;#Wt=0;#Re=new Map;#P={filtered:0,missed:0,degraded:0,discontinuities:0,resynced:0,late:0,queueResetted:0};#oe=0;#it=0;#Oe=0;#J=0;#_e=0;#Ae=0;#we=0;#ae=0;#le;#Ge=[];#ce=[];#ke=0;#ue=0;#Se=0;#fe=0;#De=R;#de=0;#C=R;#q=!1;#me=null;#Tt="";#ze=[0,0,0,0,0,0];#st=0;#Z=null;#rt=null;#nt=0;constructor(e,t={},i=null){super(),this.#e=e,this.#D=t.doubleRate??!1,this.#O=t.spatialCheck??!0,this.#G=t.debug??!1,this.#k=t.film??!1,this.#Ye=t.onStats,this.#Je=t.onFailure,this.#A=i,this.#W=i?"main":t.rendering??"main",this.#Ze=t.workerUrl??ye,this.#p=this.#W==="main"?"main":"idle",this.#r=i?i.canvas:document.createElement("canvas"),this.#t=i?.canvas??(this.#W==="main"?this.#r:document.createElement("canvas")),this.#ne=e,i||(this.#r.style.cssText="position:absolute;pointer-events:none;visibility:hidden");const s=this.#t.getContext("webgl2",{alpha:!0,antialias:!1,depth:!1,stencil:!1,preserveDrawingBuffer:!1,powerPreference:"high-performance"});if(!(s instanceof WebGL2RenderingContext))throw new Error("this browser has no WebGL2");this.#i=s,this.#k&&(this.#_t(),this.#s=new H(s)),this.#d=Y(s,me);const r=this.#d;this.#u=Object.fromEntries(Object.entries(de).map(([h,o])=>[h,s.getUniformLocation(r,o)])),this.#v=Y(s,Ue),this.#m=s.getUniformLocation(this.#v,"uField"),this.#b=s.getUniformLocation(this.#v,"uFlip"),this.#le=s.getExtension("EXT_disjoint_timer_query_webgl2"),this.#t.addEventListener("webglcontextlost",this.#$t),this.#ge=i?null:new ResizeObserver(()=>this.#Ke()),this.encodedVideo=!i&&typeof VideoDecoder<"u"?new ve(e):null,this.#h=new Te(e,()=>this.encodedVideo?.take()),e.addEventListener("emptied",this.#zt),e.addEventListener("resize",this.#Gt),e.addEventListener("pause",this.#j),e.addEventListener("ended",this.#j),e.addEventListener("seeking",this.#Xt),e.addEventListener("seeked",this.#j),e.addEventListener("ratechange",this.#j)}get running(){return this.#F&&(this.#T?.interlaced??!0)}get canvas(){return this.#r}get#yt(){return this.#T?.topFieldFirst!==!1}#Ft(){return{doubleRate:this.#D,spatialCheck:this.#O,film:this.#k,debug:this.#G}}get enabled(){return this.#Be}set enabled(e){this.#Be=e,this.#ht(),this.#f?.postMessage({type:"enabled",enabled:e})}set scan(e){const t=this.#T?.interlaced!==e?.interlaced,i=t||this.#T?.topFieldFirst!==e?.topFieldFirst;this.#T=e,!(i&&(!this.#ve()||this.#T!==e))&&(this.#f?.postMessage({type:"scan",scan:e}),i&&(this.#y=0,this.#_(),this.#X(),t&&(this.#g=0),this.#a=null,this.#Q(!1)),this.#ht(),i&&((e?.interlaced??!0)&&(this.#A||this.#p==="main")?this.#Me():this.#dt()))}get scan(){return this.#T}set videoTimeline(e){this.#re=e,this.#f?.postMessage({type:"timeline",videoTimeline:e}),e.length===0&&(this.#T=null),this.#ht()}get videoTimeline(){return this.#re}get container(){return this.#I??this.#e}get doubleRate(){return this.#D}set doubleRate(e){e!==this.#D&&(this.#D=e,this.#pe(),this.#_(),this.#Rt())}get spatialCheck(){return this.#O}set spatialCheck(e){e!==this.#O&&(this.#O=e,this.#pe())}get film(){return this.#k}set film(e){const t=this.#f?this.#rt:this.#Z;if(!(e===this.#k&&(e===!1||t===null))){if(this.#f){this.#k=e,this.#pe(e?"film":void 0);return}if(e){if(!this.#ve())return;try{this.#At()}catch(i){this.#k=!0,this.#pe(),this.#at(`film detector unavailable: ${i instanceof Error?i.message:String(i)}`);return}}if(this.#k=e,this.#pe(),!e){if(!this.#ve())return;this.#q=!1,this.#C=R,this.#X(),this.#s?.destroy(),this.#s=null}this.#Rt()}}get debug(){return this.#G}set debug(e){e!==this.#G&&(this.#G=e,this.#pe())}get#qt(){return this.#D||this.#k}#Rt(){this.#V||(this.#qt?(this.#M>0&&this.#Ot(),(this.#T?.interlaced??!0)&&(this.#A||this.#p==="main")&&this.#Me()):this.#k||(this.#a=null,this.#Q(!1),this.#Le()))}#pe(e){this.#f?.postMessage({type:"settings",options:this.#Ft(),retryFilm:e})}#_t(){if(this.#i.getExtension("EXT_color_buffer_float")===null)throw new Error("film needs EXT_color_buffer_float")}#At(){this.#_t(),this.#s??=new H(this.#i),this.#M>0&&this.#s.resize(this.#M,this.#z)}#ht(){this.#Be&&(this.#re.length>0||(this.#T?.interlaced??!0))?this.start():this.stop()}#Kt(){return this.#A||this.#W==="main"?!1:this.#p==="starting"||this.#p==="active"?!0:typeof Worker<"u"&&typeof VideoFrame<"u"&&typeof OffscreenCanvas<"u"&&this.#Ze!==null&&"transferControlToOffscreen"in HTMLCanvasElement.prototype?(this.#wt(),!0):this.#W==="auto"?(this.#Ve(),!1):(this.#p="failed",this.#F=!1,!0)}#wt(){this.#K(),this.#f?.terminate(),this.#f=null,this.#Fe=!1,this.#Ne=!1,this.#rt=null,this.#nt=0;let e=this.#r;if(this.#tt){e=document.createElement("canvas"),e.className=this.#r.className;const r=this.#r.getAttribute("style");r===null?e.removeAttribute("style"):e.setAttribute("style",r),e.style.visibility="hidden",this.#r.parentElement&&this.#r.replaceWith(e),this.#r=e}const t=++this.#et;this.#p="starting";let i,s;try{s=e.transferControlToOffscreen(),this.#tt=!0,i=new Worker(this.#Ze,{type:"module"})}catch(r){this.#Pe(r instanceof Error?r.message:String(r));return}this.#f=i,i.onmessage=r=>{t===this.#et&&this.#Qt(r.data)},i.onerror=r=>{t===this.#et&&(r.preventDefault(),this.#Pe(r.message||"the deinterlacer worker failed"))},i.postMessage({type:"initialize",canvas:s,options:this.#Ft(),scan:this.#T,videoTimeline:this.#re,enabled:this.#F,video:this.#lt()},[s])}#Qt(e){switch(e.type){case"ready":this.#p="active",this.#F&&(this.#Ce(),this.#Et());break;case"failed":this.#Pe(e.message);break;case"consumed":{this.#Fe=!1,this.#Ne=!0;const t=this.#he;this.#he=null,t&&this.#St(t);break}case"visibility":this.#r.style.visibility=e.visible?"visible":"hidden";break;case"stats":{const t={...e.stats,dropped:this.#e.getVideoPlaybackQuality?.().droppedVideoFrames??0},i=t.filmError??null,s=this.#nt;if(this.#rt=i,this.#nt=e.filmFailure,i!==null&&e.filmFailure!==s){this.dispatchEvent(new CustomEvent("failure",{detail:i}));try{this.#Je?.(i)}catch{}}this.dispatchEvent(new CustomEvent("stats",{detail:t})),this.#Ye?.(t);break}case"capture":{const t=this.#Re.get(e.id);if(this.#Re.delete(e.id),!t){e.image?.close();break}e.image?t.resolve(e.image):createImageBitmap(this.#e).then(t.resolve,t.reject);break}}}#ot(e){if(this.dispatchEvent(new CustomEvent("failure",{detail:e})),!this.#A)try{this.#Je?.(e)}catch{}}#at(e){this.#Z!==e&&(this.#Z=e,this.#q=!1,this.#C=R,this.#X(),this.#s?.destroy(),this.#s=null,this.#ot(e))}#ve(){return this.#V?!1:(this.#f||(this.#Z=null),!0)}#Pe(e){if(this.#p==="starting"&&this.#W==="auto"&&!this.#ye){this.#Ve();return}if(this.#kt(e),!this.#ye){this.#ye=!0,this.#wt();return}console.error(`Deinterlacer Worker stopped: ${e}`),this.#p="failed",this.#f?.terminate(),this.#f=null,this.#K(),this.#ot(`deinterlacer worker stopped: ${e}`),this.stop()}#Ve(){const e=this.#t;e.className=this.#r.className;const t=this.#r.getAttribute("style");t===null?e.removeAttribute("style"):e.setAttribute("style",t),e.style.visibility="hidden",this.#r.parentElement&&this.#r.replaceWith(e),this.#r=e,this.#tt=!1,this.#f?.terminate(),this.#f=null,this.#p="main",this.#K(),this.#F&&(this.#Ce(),this.#Et(),(this.#T?.interlaced??!0)&&this.#Me())}#K(){this.#he?.frame.close(),this.#he=null}#kt(e){for(const t of this.#Re.values())t.reject(new Error(e));this.#Re.clear()}start(){if(!(this.#F||this.#V||this.#N)&&(this.#Y++,this.#F=!0,this.#Vt(),!!this.#ve())){if(this.#Ie=performance.now(),this.#je=this.#Ie,this.#Ue=Number.NaN,this.#se=this.#e.getVideoPlaybackQuality?.().totalVideoFrames??0,this.#di(),this.#Et(),this.#Kt()){this.#f?.postMessage({type:"enabled",enabled:!0}),this.#p==="active"&&this.#Ce();return}this.#Ce(),(this.#T?.interlaced??!0)&&this.#Me()}}stop(){this.#Y++,this.#F&&(this.#F=!1,this.#h.cancel(),this.encodedVideo?.suspend(),this.#hi(),this.#dt(),this.#y=0,this.#a=null,this.#Q(!1),this.#K(),this.#f?.postMessage({type:"enabled",enabled:!1}))}destroy(){if(!this.#V){this.#V=!0,this.#Be=!1,this.stop(),this.#f?.postMessage({type:"destroy"}),this.#f?.terminate(),this.#f=null,this.#K(),this.#kt("the deinterlacer was destroyed"),this.#S?.removeEventListener("visibilitychange",this.#vt),this.#S=null,this.#t.removeEventListener("webglcontextlost",this.#$t),this.#h.destroy(),this.encodedVideo?.destroy(),this.#e.removeEventListener("emptied",this.#zt),this.#e.removeEventListener("resize",this.#Gt),this.#e.removeEventListener("pause",this.#j),this.#e.removeEventListener("ended",this.#j),this.#e.removeEventListener("seeking",this.#Xt),this.#e.removeEventListener("seeked",this.#j),this.#e.removeEventListener("ratechange",this.#j),this.#mi();for(const e of this.#o)this.#i.deleteTexture(e);this.#o=[],this.#Le();for(const e of[...this.#Ge,...this.#ce.map(({q:t})=>t)])this.#i.deleteQuery(e);this.#Ge.length=0,this.#ce.length=0,this.#s?.destroy(),this.#s=null,this.#me!==null&&(re(this.#me),this.#me=null),this.#i.deleteProgram(this.#d),this.#i.deleteProgram(this.#v),this.#i.getExtension("WEBGL_lose_context")?.loseContext()}}capture(){if(this.#p==="active"&&this.#r.style.visibility==="visible"&&this.#f){const s=++this.#Wt,r=new Promise((h,o)=>{this.#Re.set(s,{resolve:h,reject:o})});return this.#f.postMessage({type:"capture",id:s,width:this.#e.videoWidth,height:this.#e.videoHeight}),r}if(this.#p==="starting"||this.#p==="failed")return createImageBitmap(this.#e);const e=this.#a;if(this.#A&&(!this.#F||this.#N||!e))return Promise.reject(new Error("no rendered picture is available"));if(!this.#F||this.#N||!e)return createImageBitmap(this.#e);e.kind==="texture"?this.#gt(e.texture,e.flip,!1):this.#ee(e.flush,e.second,null,!1);const t=this.#e.videoWidth,i=this.#e.videoHeight;return t>0&&i>0&&(t!==this.#t.width||i!==this.#t.height)?createImageBitmap(this.#t,{resizeWidth:t,resizeHeight:i,resizeQuality:"high"}):createImageBitmap(this.#t)}addEventListener(e,t,i){super.addEventListener(e,t,i)}removeEventListener(e,t,i){super.removeEventListener(e,t,i)}#Ce(){this.#A||!this.#F||this.#h.request(this.#ii)}#lt(){const e=[];for(let t=0;t<this.#e.buffered.length;t++)e.push({start:this.#e.buffered.start(t),end:this.#e.buffered.end(t)});return{currentTime:this.#e.currentTime,playbackRate:this.#e.playbackRate,seeking:this.#e.seeking,paused:this.#e.paused,ended:this.#e.ended,readyState:this.#e.readyState,videoWidth:this.#e.videoWidth,videoHeight:this.#e.videoHeight,buffered:e}}#jt(e,t,i){let s;try{s=i?.clone()??new VideoFrame(this.#e,{timestamp:Math.max(0,Math.round(t.mediaTime*1e6))})}catch(h){const o=h instanceof Error?h.message:String(h);this.#W==="auto"&&!this.#Ne&&!this.#ye?(this.#Ve(),this.#$e(e,t)):this.#Pe(o);return}const r={id:++this.#Ht,frame:s,now:e,metadata:t,video:this.#lt()};if(this.#Fe){this.#he?.frame.close(),this.#he=r;return}this.#St(r)}#St(e){const t=this.#f;if(!t||this.#p!=="active"){e.frame.close();return}this.#Fe=!0;const i={type:"frame",id:e.id,frame:e.frame,metadata:e.metadata,video:e.video};try{t.postMessage(i,[e.frame])}catch(s){this.#Fe=!1,e.frame.close();const r=s instanceof Error?s.message:String(s);this.#W==="auto"&&!this.#Ne&&!this.#ye?(this.#Ve(),this.#$e(e.now,e.metadata)):this.#Pe(r)}}#Yt(e,t,i){this.#me==null&&(this.#me=ie(this.#i,"20px monospace")),ne(this.#me,e,t,i,this.#M,this.#z,20)}#Dt(e){if(this.#le==null||this.#ce.length>30)return;const t=this.#Ge.pop()??this.#i.createQuery();return this.#i.beginQuery(this.#le.TIME_ELAPSED_EXT,t),this.#ce.push({q:t,isField:e}),t}#Xe(e){this.#le!=null&&(e!=null&&this.#i.endQuery(this.#le.TIME_ELAPSED_EXT),this.#ce=this.#ce.filter(({q:t,isField:i})=>{if(this.#i.getQueryParameter(t,this.#i.QUERY_RESULT_AVAILABLE)){const s=this.#i.getQueryParameter(t,this.#i.QUERY_RESULT);return i?(this.#Se+=s,this.#fe++):(this.#ke+=s,this.#ue++),this.#Ge.push(t),!1}return!0}))}#X(){this.#C=R,this.#De=R,this.#de=0,this.#q=!1,this.#s?.reset()}#Jt(){const{cur:e,next:t}=this.#Bt(!1),i=this.#o[e],s=this.#o[t];if(!i||!s)return;const r=this.#T?.topFieldFirst!==!1?0:1;this.#s?.detect(i,s,r)}#Zt(){const e=this.#s?.poll()??null;e!==null&&(this.#De=e,this.#de=e.age),this.#de++;const{phase:t,run:i}=this.#De;t===0||this.#de>Math.ceil(O*Math.max(1,this.#e.playbackRate))?this.#C=R:this.#C={phase:(t-1+this.#de)%O+1,run:i}}#ei(e){const t=[],i=this.#s?.metrics??new Float32Array(0);for(let r=0;r<d.phase;r++){const h=i[r*4]??0,o=i[r*4+1]??0,l=i[r*4+2]??0;t.push(`${h.toFixed(3)},${o.toString().padStart(4)},${l.toFixed(3)}`)}const s=this.#ze.map((r,h)=>`${h===0?"-":h}:${r}`).join(" ");return`frame=${e} phase=${this.#C.phase} run=${this.#C.run} known=${this.#De.phase}/${this.#De.run} age=${this.#de} ${this.#q?"film":"video"} period=${this.#g.toFixed(3)}
${t.join(" ")}
${s} dropped:${this.#st}`}#ct(e,t){const i=t-performance.timeOrigin;return Number.isFinite(i)&&i!==0?e+i:e}#ti(e,t){const i=e.expectedDisplayTime;if(!Number.isFinite(i)||i<=0||!Number.isFinite(e.timeOrigin))return t;const s=this.#ct(i,e.timeOrigin),r=Ce*Math.max(this.#R,this.#g);return s<t-r||s>t+r?t:s}#ii=(e,t)=>{if(!this.#F||this.#N)return;this.#pt();const i=this.#ct(e,t.timeOrigin);this.#Ie=i,this.#se=Math.max(this.#se,this.#e.getVideoPlaybackQuality?.().totalVideoFrames??0);const{frame:s,...r}=t;this.#ne=s??this.#e;try{this.#Pt(i,r,s)}finally{this.#ne=this.#e}this.#Ce()};#Pt(e,t,i){if(this.#Ue=t.mediaTime,this.#p==="active"){this.#jt(e,t,i);return}this.#p!=="starting"&&this.#$e(e,t)}ingestExternalFrame(e,t,i){this.#ne=i;try{this.#$e(e,t)}finally{this.#ne=this.#e}}#$e(e,t){const i=this.#Y;if(this.#$(i)&&(this.#si(t.mediaTime),!!this.#$(i)&&t.width>0&&t.height>0)){let s=!1;if(!this.#Te&&this.#e.seeking){const c=this.#e.buffered,p=this.#g>=N?this.#g/1e3:C/1e3;for(let v=0;v<c.length;v++)if(t.mediaTime>=c.start(v)&&t.mediaTime<c.end(v)&&Math.abs(t.mediaTime-this.#e.currentTime)<=p){s=!0;break}}if(s&&(this.#Te=!0),(this.#M===0||this.#z===0)&&this.#Nt(t.width,t.height),!this.#$(i))return;if(this.#T&&!this.#T.interlaced){this.#ci();return}const r=t.mediaTime-this.#be,h=t.mozTiming,o=s||(h?h.discontinuity||r<0||r>q:r<0||r>q);o&&(this.#y=0,this.#g=0,this.#P.discontinuities++,this.#_(),this.#X());const l=this.#ui(t.presentedFrames,o);if(this.#y>0&&t.mediaTime===this.#be&&(!h||t.presentedFrames===this.#Qe))return;if(!o){const c=h?.periodMs??0;c>0?this.#Ct(c*(this.#e.playbackRate||1)/1e3,1):this.#y>0&&r>0&&this.#Ct(r,l+1)}this.#be=t.mediaTime,this.#Qe=t.presentedFrames;const u=performance.now();u-this.#it>K&&(this.#Oe=u,this.#J=0,this.#_e=0,this.#Ae=0,this.#we=0,this.#ae=0,this.#ie=0,this.#ke=0,this.#ue=0,this.#Se=0,this.#fe=0),this.#it=u;const a=performance.now(),m=this.#Dt(!1);if(this.#It(),this.#k&&!this.#Z&&!this.#s)try{this.#At()}catch(c){this.#at(`film detector unavailable: ${c instanceof Error?c.message:String(c)}`)}if(!this.#$(i)){this.#V||this.#Xe(m);return}if(this.#k&&!this.#Z){if(this.#y===T&&l===0)try{this.#Zt(),this.#Jt()}catch(c){this.#at(`film detection failed: ${c instanceof Error?c.message:String(c)}`)}else this.#X();this.#ze[this.#C.phase]=(this.#ze[this.#C.phase]??0)+1,this.#q=this.#C.phase!==0&&this.#C.run>=U,this.#G&&(this.#Tt=this.#ei(t.presentedFrames))}if(!this.#$(i)){this.#V||this.#Xe(m);return}const f=this.#ti(t,e)+this.#R;if(this.#q)if(this.#He()){const c=this.#C.phase;if(c===L)this.#st++,this.#te++;else{const p=this.#g*O/Me,v=this.#ft(1,e,p),x=Le[c]??0,G=v||this.#B===null?f+p:f+x*this.#g;this.#We("film",!1,this.#ut("film",G,p),p)}}else this.#ee(!1,!1,null);else if(this.#D&&this.#He()){const c=this.#g/2,v=this.#ft(2,e,c)||this.#B===null?f+c*2:f,x=this.#ut("field",v,c);this.#We("field",!1,x,c),this.#We("field",!0,x+c,c)}else if(this.#He()){const c=this.#g,v=this.#ft(1,e,c)||this.#B===null?f+c:f;this.#We("frame",!1,this.#ut("frame",v,c),c)||(this.#P.late++,this.#ee(!1,!1,null))}else this.#P.late+=this.#n.length,this.#_(),this.#ee(!1,!1,null);this.#ae=Math.max(this.#ae,this.#n.length),this.#Xe(m),this.#_e+=performance.now()-a,this.#J++,this.#fi(u)}}#$(e){return!this.#V&&this.#F&&e===this.#Y}#si(e){const t=this.#Y;let i;for(let h=this.#re.length-1;h>=0;h--){const o=this.#re[h];if(o.start<=e+1e-6){i=o;break}}if(i?.codedSize&&(i.codedSize.width!==this.#M||i.codedSize.height!==this.#z)&&this.#Nt(i.codedSize.width,i.codedSize.height),!this.#$(t))return;const s=i?.scan;if(!s||this.#T?.interlaced===s.interlaced&&this.#T.topFieldFirst===s.topFieldFirst)return;const r=this.#T?.interlaced;this.#T=s,this.#y=0,this.#_(),this.#ve()&&(r!==s.interlaced&&(this.#g=0),s.interlaced&&(this.#A||this.#p==="main")?this.#Me():this.#dt(),this.#X())}#He(){return(this.#D||this.#k)&&this.#g>0&&this.#l.length===A}#Ct(e,t){const s=e*1e3/(this.#e.playbackRate||1)/t;s<N||s>C||(this.#g=this.#g>0&&s>this.#g*ke?this.#g+(s-this.#g)*Fe:s)}#We(e,t,i,s){const r=this.#Mt();if(r===null)return!1;const h=this.#l[r];if(!h)return!1;for(this.#E=r;this.#n.length>0&&this.#n[0]?.slot===r;)this.#n.shift(),this.#P.late++;this.#ee(!1,t,h.framebuffer);const o={slot:r,at:i,duration:s,cadence:e,phase:e==="film"?this.#C.phase:e==="field"?t?2:1:0,droppedBefore:this.#te};return this.#te=0,this.#n.push(o),this.#B=o,!0}#ut(e,t,i){if(!(i>0))return t;const s=this.#B;if(s!==null&&s.cadence===e){const r=s.at+s.duration,h=t-r;if(Math.abs(h)<i){const o=Math.max(-Q,Math.min(Q,h*Se));return r+o}}s!==null&&this.#P.resynced++;for(let r=this.#n.at(-1);r&&r.at>=t;)this.#n.pop(),this.#P.late++,r=this.#n.at(-1);return t}#ft(e,t,i){const s=this.#n.at(-1),r=(B+1)*Math.max(this.#R,i);if(s&&s.at-t>r)return this.#_(),this.#P.queueResetted++,!0;const h=Math.max(0,this.#n.length+e-B);let o=0,l=0;for(;l<h;){const u=this.#n.shift();if(!u)break;o+=u.duration,l++}for(const u of this.#n)u.at-=o;return this.#P.late+=l,!1}#Mt(){const e=this.#a?.kind==="texture"?this.#a.texture:null,t=new Set(this.#n.map(({slot:s})=>s));for(let s=1;s<=A;s++){const r=(this.#E+s)%A,h=this.#l[r];if(h&&h.texture!==e&&!t.has(r))return r}const i=this.#n[0];if(i){const s=this.#l[i.slot];if(s&&s.texture!==e)return i.slot}return null}#Me(){this.#c===null&&(!this.#F||this.#N||(this.#x=0,this.#c=this.#Ee(this.#mt)))}#dt(){this.#qe(this.#c),this.#c=null,this.#_()}#mt=e=>{if(this.#c=null,!this.#F||this.#N)return;this.#ri(e);const t=this.#Y;this.#h.flush(e),this.#$(t)&&(this.#p==="main"&&this.#ai(this.#H,e),this.#c=this.#Ee(this.#mt))};#ri(e){const t=e-this.#x;this.#x=e;const i=Math.max(1,Math.round(t/this.#R)),s=this.#H+i*this.#R,r=e-s;if(this.#H===0||t<=0||t>C||Math.abs(r)>this.#R/4){t>=1&&t<=C&&(this.#R=t),this.#H=e;return}this.#R+=r/i*De,this.#H=s+r*Pe}#Lt(){const e=this.#A;if(e)return{frames:e,origin:performance.timeOrigin};const t=this.#r.ownerDocument?.defaultView??this.#e.ownerDocument?.defaultView??null;return t===null?{frames:Ie,origin:performance.timeOrigin}:{frames:t,origin:t.performance.timeOrigin}}#Ee(e){const{frames:t,origin:i}=this.#Lt(),s=t.requestAnimationFrame(r=>e(this.#ct(r,i)));return{frames:t,handle:s}}#qe(e){e?.frames.cancelAnimationFrame(e.handle)}#pt(){if(this.#A)return;this.#ni();const{frames:e}=this.#Lt(),t=this.#c!==null&&this.#c.frames!==e,i=this.#w!==null&&this.#w.frames!==e;!t&&!i||(this.#x=0,t&&(this.#qe(this.#c),this.#c=this.#Ee(this.#mt)),i&&(this.#qe(this.#w),this.#w=this.#Ee(this.#xt)))}#ni(){const e=this.#A?null:this.#r.ownerDocument??null;e!==this.#S&&(this.#S?.removeEventListener("visibilitychange",this.#vt),this.#S=e,e?.addEventListener("visibilitychange",this.#vt))}#vt=()=>{this.#V||this.#pt()};#Et(){this.#A||this.#w!==null||!this.#F||this.#N||(this.#w=this.#Ee(this.#xt))}#hi(){this.#qe(this.#w),this.#w=null}#xt=e=>{if(this.#w=null,!this.#F||this.#N)return;const t=this.#Y;this.#h.flush(e),this.#$(t)&&(this.#oi(e),this.#$(t)&&(this.#w=this.#Ee(this.#xt)))};#oi(e){if(this.#A||this.#h.captureDriven||this.#h.mozDriven&&this.#h.hasDelivered||e-this.#Ie<_e||this.#e.paused||this.#e.ended||this.#e.readyState<2)return;const t=this.#e.currentTime,i=this.#e.getVideoPlaybackQuality?.().totalVideoFrames??0,s=this.#g>=N?this.#g:Ae,r=i>this.#se,h=t!==this.#Ue&&e-this.#je>=s*.75;!r&&!h||(this.#se=Math.max(this.#se,i),this.#je=e,this.#Pt(e,{mediaTime:t,presentedFrames:Math.max(this.#oe+1,i),expectedDisplayTime:e,timeOrigin:performance.timeOrigin,width:this.#e.videoWidth,height:this.#e.videoHeight}))}#ai(e,t){const i=this.#R/2,s=l=>{const u=l.at-e;return u<=i-j?!0:u>i+j?!1:this.#xe>0};for(;this.#n[1]&&s(this.#n[1]);)this.#P.late++,this.#n.shift();const r=this.#n[0];if(!r||!s(r))return;this.#n.shift(),this.#xe=r.at-e;const h=performance.now(),o=this.#Dt(!0);this.#Ut(r.slot),this.#Xe(o),this.#we+=performance.now()-h,this.#Ae++,this.#G&&this.#li(r,t),this.#U=t}#li(e,t){const i=this.#U===0?0:t-this.#U,s=i/this.#R,r=e.cadence==="film"?`phase ${e.phase}`:e.cadence==="field"?`field ${e.phase}`:"frame",h=e.phase===0?"duplicate":`phase ${L}`,o=e.droppedBefore>0?`, ${h} dropped before it`+(e.droppedBefore>1?` (${e.droppedBefore})`:""):"";console.log(`yadif: +${i.toFixed(2)} ms (${s.toFixed(2)} refreshes) ${e.cadence} ${r}, due ${(e.at-t).toFixed(2)} ms${o}`)}#Ut(e){const t=this.#l[e];t&&this.#gt(t.texture)}#ci(){this.#It();const e=this.#o[this.#L];e&&this.#gt(e,!0),this.#y=0}#Q(e){if(this.#A){this.#A.onVisibility(e);return}this.#r.style.visibility=e?"visible":"hidden"}#gt(e,t=!1,i=!0){const s=this.#i;s.bindFramebuffer(s.FRAMEBUFFER,null),s.useProgram(this.#v),s.activeTexture(s.TEXTURE0),s.bindTexture(s.TEXTURE_2D,e),s.uniform1i(this.#m,0),s.uniform1i(this.#b,t?1:0),s.viewport(0,0,this.#M,this.#z),s.drawArrays(s.TRIANGLES,0,3),this.#a={kind:"texture",texture:e,flip:t},this.#Q(!0),i&&this.#ie++}#ui(e,t){let i=0;return this.#oe!==0&&!t&&(i=Math.max(0,e-this.#oe-1),this.#P.missed+=i),this.#oe=e,i}#fi(e){const t=e-this.#Oe;if(t<K)return;const i=this.#He()&&(this.#D||this.#q)?this.#Ae:this.#J,s=this.#J?(this.#_e+this.#we)/this.#J:0;let r;this.#le!=null&&(r=0,this.#ue!==0&&(r+=this.#ke/1e6/this.#ue),this.#fe!==0&&(r+=this.#Se/1e6/this.#fe/2));const h={...this.#P,dropped:this.#e.getVideoPlaybackQuality?.().droppedVideoFrames??0,fps:i*1e3/t,frameMs:s,maxQueuedFields:this.#ae,outputFps:this.#ie*1e3/t,gpuMs:r,film:this.#q,filmError:this.#Z};this.dispatchEvent(new CustomEvent("stats",{detail:h})),this.#Ye?.(h),this.#Oe=e,this.#J=0,this.#_e=0,this.#Ae=0,this.#we=0,this.#ae=0,this.#ie=0,this.#ke=0,this.#ue=0,this.#Se=0,this.#fe=0}#It(){const e=this.#i;this.#L=(this.#L+1)%T,e.bindTexture(e.TEXTURE_2D,this.#o[this.#L]??null),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,this.#ne),this.#y=Math.min(this.#y+1,T)}#ee(e,t,i,s=!0){if(this.#y===0||this.#N)return;s&&(this.#y===T&&!e?this.#P.filtered++:this.#P.degraded++);const r=this.#i,{prev:h,cur:o,next:l}=this.#Bt(e);r.bindFramebuffer(r.FRAMEBUFFER,i),r.useProgram(this.#d);for(const[E,f]of[h,o,l].entries())r.activeTexture(r.TEXTURE0+E),r.bindTexture(r.TEXTURE_2D,this.#o[f]??null);r.uniform1i(this.#u.prev,0),r.uniform1i(this.#u.cur,1),r.uniform1i(this.#u.next,2);const u=this.#k?this.#s?.texture??null:null,a=u!==null;u!==null&&(r.activeTexture(r.TEXTURE0+3),r.bindTexture(r.TEXTURE_2D,u),r.uniform1i(this.#u.fieldMetrics,3)),r.uniform2i(this.#u.size,this.#M,this.#z);const m=this.#yt?0:1;r.uniform1i(this.#u.parity,t?1-m:m),r.uniform1i(this.#u.tff,this.#yt?1:0),r.uniform1i(this.#u.second,t?1:0),r.uniform1i(this.#u.spatialCheck,this.#O?1:0),r.uniform1i(this.#u.debug,this.#G?1:0),r.uniform1i(this.#u.film,a?1:0),r.uniform1i(this.#u.phase,this.#C.phase),r.viewport(0,0,this.#M,this.#z),r.drawArrays(r.TRIANGLES,0,3),this.#G&&a&&this.#Yt(this.#Tt,0,90),i===null&&(this.#a={kind:"yadif",flush:e,second:t},this.#Q(!0),s&&this.#ie++)}#Bt(e){const t=i=>(this.#L+T-i)%T;return this.#y===1?{prev:this.#L,cur:this.#L,next:this.#L}:e?{prev:t(1),cur:this.#L,next:this.#L}:this.#y===2?{prev:t(1),cur:t(1),next:this.#L}:{prev:t(2),cur:t(1),next:this.#L}}#Ke(){if(this.#pt(),!this.#I)return;const e=this.#e,t=e.videoWidth,i=e.videoHeight;if(t===0||i===0)return;const s=Math.min(e.offsetWidth/t,e.offsetHeight/i),r=t*s,h=i*s;this.#r.style.left=`${e.offsetLeft+(e.offsetWidth-r)/2}px`,this.#r.style.top=`${e.offsetTop+(e.offsetHeight-h)/2}px`,this.#r.style.width=`${r}px`,this.#r.style.height=`${h}px`}#Nt(e,t){const i=this.#i;this.#t.width=e,this.#t.height=t,this.#M=e,this.#z=t,this.#y=0,this.#a=null,this.#_(),this.#Ke();for(const s of this.#o)i.deleteTexture(s);this.#o=[];for(let s=0;s<T;s++){const r=i.createTexture();i.bindTexture(i.TEXTURE_2D,r),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MAG_FILTER,i.NEAREST),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_S,i.CLAMP_TO_EDGE),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_T,i.CLAMP_TO_EDGE),i.texImage2D(i.TEXTURE_2D,0,i.RGBA,e,t,0,i.RGBA,i.UNSIGNED_BYTE,null),this.#o.push(r)}this.#Le(),(this.#D||this.#k)&&this.#Ot(),this.#s?.resize(e,t),this.#ve()}#Ot(){const e=this.#i;if(!(this.#l.length===A||this.#M===0)){this.#Le();for(let t=0;t<A;t++){const i=e.createTexture();e.bindTexture(e.TEXTURE_2D,i),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.NEAREST),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.NEAREST),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,this.#M,this.#z,0,e.RGBA,e.UNSIGNED_BYTE,null);const s=e.createFramebuffer();e.bindFramebuffer(e.FRAMEBUFFER,s),e.framebufferTexture2D(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0,e.TEXTURE_2D,i,0);const r=e.checkFramebufferStatus(e.FRAMEBUFFER)===e.FRAMEBUFFER_COMPLETE;if(e.bindFramebuffer(e.FRAMEBUFFER,null),!r){e.deleteFramebuffer(s),e.deleteTexture(i),this.#Le();return}this.#l.push({texture:i,framebuffer:s})}this.#E=A-1}}#Le(){const e=this.#i,t=this.#a?.kind==="texture"?this.#a.texture:null;this.#l.some(i=>i.texture===t)&&(this.#a=null);for(const{texture:i,framebuffer:s}of this.#l)e.deleteFramebuffer(s),e.deleteTexture(i);this.#l=[],this.#_()}#di(){if(this.#I)return;const e=this.#e.parentElement;if(!e)return;const t=document.createElement("div");t.style.cssText="position:relative;display:inline-block;line-height:0;max-width:100%",e.insertBefore(t,this.#e),t.appendChild(this.#e),t.appendChild(this.#r),this.#I=t,this.#ge?.observe(this.#e),this.#Ke()}#mi(){if(this.#A)return;const e=this.#I;this.#I=null,this.#ge?.disconnect(),this.#r.remove(),e?.parentElement&&(e.parentElement.insertBefore(this.#e,e),e.remove())}#Gt=()=>this.#Ke();#bt(e){return!this.#f||this.#p==="main"?!1:(this.#f.postMessage({type:"event",name:e,video:this.#lt()}),!0)}#zt=()=>{if(this.#Ue=Number.NaN,this.#bt("emptied")){this.#K(),this.#Q(!1);return}this.#y=0,this.#be=0,this.#Qe=0,this.#_(),this.#X(),this.#g=0,this.#Vt(),this.#a=null,this.#Q(!1)};#Vt(){this.#P={filtered:0,missed:0,degraded:0,discontinuities:0,resynced:0,late:0,queueResetted:0},this.#ze.fill(0),this.#st=0,this.#oe=0,this.#Oe=0,this.#it=0,this.#J=0,this.#_e=0,this.#Ae=0,this.#we=0,this.#ae=0,this.#ie=0,this.#_(),this.#ke=0,this.#ue=0,this.#Se=0,this.#fe=0}#Xt=()=>{if(this.#bt("seeking")){this.#K();return}this.#Te=!1};#j=e=>{if((e.type==="pause"||e.type==="ended"||e.type==="seeked"||e.type==="ratechange")&&this.#bt(e.type)){this.#K();return}if(e.type==="seeked"){const i=this.#Te;if(this.#Te=!1,i)return;this.#y=0,this.#_(),this.#X(),this.#a=null,this.#Q(!1);return}const t=e.type==="ratechange";if(t&&(this.#g=0,this.#be=this.#e.currentTime),this.#_(),this.#F&&this.#y>0){const i=this.#Mt(),s=i===null?void 0:this.#l[i];i!==null&&s?(this.#E=i,this.#ee(!0,!1,s.framebuffer),this.#Ut(i)):this.#ee(!0,!1,null)}t&&(this.#y=0,this.#oe=0,this.#X())};#$t=e=>{if(e.preventDefault(),this.#A){this.#A.onFailure("the deinterlacer WebGL context was lost");return}this.#p!=="active"&&(this.#N=!0,this.#ot("the deinterlacer WebGL context was lost"),this.stop())}}function Ne(n,e,t,i,s,r,h){return new Be(n,t,{canvas:e,onFailure:i,onVisibility:s,requestAnimationFrame:r,cancelAnimationFrame:h})}function Y(n,e){const t=n.createProgram(),i=J(n,n.VERTEX_SHADER,we),s=J(n,n.FRAGMENT_SHADER,e);if(n.attachShader(t,i),n.attachShader(t,s),n.linkProgram(t),n.deleteShader(i),n.deleteShader(s),!n.getProgramParameter(t,n.LINK_STATUS)){const r=n.getProgramInfoLog(t);throw n.deleteProgram(t),new Error(`the deinterlacer failed to link: ${r??"no reason given"}`)}return t}function J(n,e,t){const i=n.createShader(e);if(!i)throw new Error("the deinterlacer could not create a shader");if(n.shaderSource(i,t),n.compileShader(i),!n.getShaderParameter(i,n.COMPILE_STATUS)){const s=n.getShaderInfoLog(i);throw n.deleteShader(i),new Error(`the deinterlacer failed to compile: ${s??"no reason given"}`)}return i}const w=self;class Oe extends EventTarget{currentTime=0;playbackRate=1;seeking=!1;paused=!0;ended=!1;readyState=0;videoWidth=0;videoHeight=0;parentElement=null;offsetWidth=0;offsetHeight=0;offsetLeft=0;offsetTop=0;#t=[];update(e){this.currentTime=e.currentTime,this.playbackRate=e.playbackRate,this.seeking=e.seeking,this.paused=e.paused,this.ended=e.ended,this.readyState=e.readyState,this.videoWidth=e.videoWidth,this.videoHeight=e.videoHeight,this.#t=e.buffered}get buffered(){return{length:this.#t.length,start:e=>{const t=this.#t[e];if(!t)throw new DOMException("Invalid range index","IndexSizeError");return t.start},end:e=>{const t=this.#t[e];if(!t)throw new DOMException("Invalid range index","IndexSizeError");return t.end}}}getVideoPlaybackQuality(){return{creationTime:performance.now(),droppedVideoFrames:0,totalVideoFrames:0,corruptedVideoFrames:0}}requestVideoFrameCallback(){return 0}cancelVideoFrameCallback(){}}let b=null,g=null,Z=!1;function Ge(n){return w.requestAnimationFrame(n)}function ze(n){w.cancelAnimationFrame(n)}function y(n,e=[]){w.postMessage(n,e)}function Ve(n,e,t){n.doubleRate=e.doubleRate,n.spatialCheck=e.spatialCheck,(n.film!==e.film||t==="film")&&(n.film=e.film),n.debug=e.debug}w.onmessage=n=>{const e=n.data;try{if(e.type==="initialize"){if(typeof w.requestAnimationFrame!="function")throw new Error("requestAnimationFrame is unavailable in this Worker");b=new Oe,b.update(e.video),g=Ne(b,e.canvas,e.options,i=>{Z||y({type:"failed",message:i})},i=>y({type:"visibility",visible:i}),Ge,ze);let t=0;g.addEventListener("failure",()=>t++),g.addEventListener("stats",i=>{const{dropped:s,...r}=i.detail;y({type:"stats",stats:r,filmFailure:t})}),g.scan=e.scan,g.videoTimeline=e.videoTimeline,g.enabled=e.enabled,y({type:"ready"});return}if(!b||!g)return;switch(e.type){case"frame":b.update(e.video);try{g.ingestExternalFrame(performance.now(),e.metadata,e.frame)}finally{e.frame.close(),y({type:"consumed",id:e.id})}break;case"settings":Ve(g,e.options,e.retryFilm);break;case"scan":g.scan=e.scan;break;case"timeline":g.videoTimeline=e.videoTimeline;break;case"enabled":g.enabled=e.enabled;break;case"event":b.update(e.video),b.dispatchEvent(new Event(e.name));break;case"capture":b.videoWidth=e.width,b.videoHeight=e.height,g.capture().then(t=>y({type:"capture",id:e.id,image:t},[t])).catch(()=>y({type:"capture",id:e.id,image:null}));break;case"destroy":Z=!0,g.destroy(),g=null,b=null,w.close();break}}catch(t){const i=t instanceof Error?t.message:String(t);y({type:"failed",message:i})}}})();
//# sourceMappingURL=worker-D1333Nr8.js.map
