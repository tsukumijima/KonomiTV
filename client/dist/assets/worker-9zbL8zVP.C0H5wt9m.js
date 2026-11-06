(function(){"use strict";const M=`#version 300 es
void main() {
  // From the vertex index alone. There is no geometry here worth a buffer.
  vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
`;function k(n,e,t){const i=n.createProgram(),s=G(n,n.VERTEX_SHADER,t),r=G(n,n.FRAGMENT_SHADER,e);if(n.attachShader(i,s),n.attachShader(i,r),n.linkProgram(i),n.deleteShader(s),n.deleteShader(r),!n.getProgramParameter(i,n.LINK_STATUS)){const o=n.getProgramInfoLog(i);throw n.deleteProgram(i),new Error(`the deinterlacer failed to link: ${o??"no reason given"}`)}return i}function G(n,e,t){const i=n.createShader(e);if(!i)throw new Error("the deinterlacer could not create a shader");if(n.shaderSource(i,t),n.compileShader(i),!n.getShaderParameter(i,n.COMPILE_STATUS)){const s=n.getShaderInfoLog(i);throw n.deleteShader(i),new Error(`the deinterlacer failed to compile: ${s??"no reason given"}`)}return i}const te=`#version 300 es
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
`,ie=`#version 300 es
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
`;function se(n,e){const t=k(n,te,ie),i=n.getAttribLocation(t,"aVertexPosition"),s=n.getAttribLocation(t,"aTextureCoord"),r=n.getUniformLocation(t,"uTexture"),o=n.getUniformLocation(t,"uMatrix"),h=n.getUniformLocation(t,"uUvMatrix"),u=n.getUniformLocation(t,"uTextColor"),f=n.getUniformLocation(t,"uBackColor");if(r==null||o==null||h==null||u==null||f==null)throw new Error("failed to initialize DEBUG_FRAGMENT_SHADER, DEBUG_VERTEX_SHADER");const a=n.createBuffer(),m=n.createBuffer();return{gl:n,...re(n,e),program:t,programUniforms:{vertex:i,textureCoord:s,texture:r,matrix:o,uvMatrix:h,textColor:u,backColor:f},positionBuffer:a,textureBuffer:m}}function re(n,e){const t=new OffscreenCanvas(0,0),i=t.getContext("2d"),s=new Map;let r=0;const o=0;let h=1;i.font=e,i.fillStyle="white";for(let f=32;f<128;f++){const a=String.fromCharCode(f),m=i.measureText(a),x=Math.ceil(m.actualBoundingBoxDescent+m.actualBoundingBoxAscent+1),c=Math.ceil(m.actualBoundingBoxLeft+m.actualBoundingBoxRight+1);s.set(a,{x:r,y:o,width:c,height:x,metrics:m}),h=Math.max(h,x),r+=c}t.width=r,t.height=h,i.font=e,i.fillStyle="white";for(const[f,a]of s)i.fillText(f,Math.floor(a.x+a.metrics.actualBoundingBoxLeft+1),Math.floor(a.metrics.actualBoundingBoxAscent+1));const u=n.createTexture();return n.bindTexture(n.TEXTURE_2D,u),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MIN_FILTER,n.LINEAR),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MAG_FILTER,n.LINEAR),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_WRAP_S,n.CLAMP_TO_EDGE),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_WRAP_T,n.CLAMP_TO_EDGE),n.texImage2D(n.TEXTURE_2D,0,n.RGBA,n.RGBA,n.UNSIGNED_BYTE,t),{fontTexture:u,chars:s,textureSize:{width:r,height:h}}}function ne(n){const e=n.gl;e.deleteBuffer(n.positionBuffer),e.deleteBuffer(n.textureBuffer),e.deleteTexture(n.fontTexture),e.deleteProgram(n.program)}function oe(n,e,t,i,s,r,o){const h=[],u=[],f=t;for(const x of e){if(x===`
`){t=f,i+=o;continue}const c=n.chars.get(x);if(c==null)continue;if(c.width===1){t+=c.metrics.width;continue}const l=Math.floor(t-c.metrics.actualBoundingBoxLeft),p=Math.floor(i-c.metrics.actualBoundingBoxAscent),v=l+c.width,E=p+c.height;h.push(l,p),u.push(c.x,c.y),h.push(l,E),u.push(c.x,c.y+c.height),h.push(l+c.width,E),u.push(c.x+c.width,c.y+c.height),h.push(v,E),u.push(c.x+c.width,c.y+c.height),h.push(l,p),u.push(c.x,c.y),h.push(v,p),u.push(c.x+c.width,c.y),t+=c.metrics.width}const a=n.gl;a.useProgram(n.program),a.bindBuffer(a.ARRAY_BUFFER,n.positionBuffer),a.bufferData(a.ARRAY_BUFFER,new Float32Array(h),a.STATIC_DRAW),a.vertexAttribPointer(n.programUniforms.vertex,2,a.FLOAT,!1,0,0),a.enableVertexAttribArray(n.programUniforms.vertex),a.bindBuffer(a.ARRAY_BUFFER,n.textureBuffer),a.bufferData(a.ARRAY_BUFFER,new Float32Array(u),a.STATIC_DRAW),a.vertexAttribPointer(n.programUniforms.textureCoord,2,a.FLOAT,!1,0,0),a.enableVertexAttribArray(n.programUniforms.textureCoord),a.activeTexture(a.TEXTURE0),a.bindTexture(a.TEXTURE_2D,n.fontTexture),a.uniform1i(n.programUniforms.texture,0),a.uniform3fv(n.programUniforms.textColor,[1,1,1]),a.uniform3fv(n.programUniforms.backColor,[0,0,0]);function m(x,c,l){const p=[];for(let v=0;v<c;v++)for(let E=0;E<x;E++)p.push(l[E*x+v]);return p}a.uniformMatrix4fv(n.programUniforms.matrix,!1,m(4,4,[1/(s/2),0,0,-1,0,-2/r,0,1,0,0,1,0,0,0,0,1])),a.uniformMatrix3fv(n.programUniforms.uvMatrix,!1,m(3,3,[1/n.textureSize.width,0,0,0,1/n.textureSize.height,0,0,0,1])),a.viewport(0,0,s,r),a.enable(a.BLEND),a.blendFunc(a.SRC_ALPHA,a.ONE_MINUS_SRC_ALPHA),a.drawArrays(a.TRIANGLES,0,h.length/2),a.disable(a.BLEND)}const d={firstRepeatsPrevious:0,secondRepeatsNext:1,secondRepeatsPrevious:2,previousSecondRepeated:3,firstRepeatsNext:4,previousFirstRepeated:5,phase:6},F=7,X=2,U=1,he=2,I=10,ae={a:"uA",b:"uB",fieldMetrics:"uFieldMetrics",first:"uFirst",size:"uSize"},$=16,V=8,le=`#version 300 es

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
  const int BLOCK_W = ${$};
  const int BLOCK_H = ${V};

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
`,ue={second:"uSecond",first:"uFirst",size:"uSize"},C=8,ce=`#version 300 es
precision highp float;

uniform sampler2D uSecond;
uniform sampler2D uFirst;

uniform ivec2 uSize;

layout(location = 0) out vec4 outSecond;
layout(location = 1) out vec4 outFirst;

void main()
{
  ivec2 dst = ivec2(gl_FragCoord.xy);
  ivec2 base = dst * ${C};

  vec4 second = vec4(0.0);
  vec4 first = vec4(0.0);

  for (int y = 0; y < ${C}; ++y) {
    for (int x = 0; x < ${C}; ++x) {
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
`,fe={previous:"uPrevious",second:"uSecond",first:"uFirst",size:"uSize"},de=`#version 300 es
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
  return differing <= ${X}.0;
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
  bool believed = run >= ${I}.0;
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
`,R=16,me=8,pe={prev:"uPrev",cur:"uCur",first:"uFirst",size:"uSize"},ve=`#version 300 es
precision highp float;
precision highp int;

uniform sampler2D uPrev;
uniform sampler2D uCur;
/** The parity of the lines of the field captured first. */
uniform int uFirst;
uniform ivec2 uSize;

out vec4 outValue;

const float COMB = 8.0 / 255.0;

float luma(sampler2D image, int x, int y) {
  int line = y < 0 ? -y : (y >= uSize.y ? 2 * (uSize.y - 1) - y : y);
  vec3 c = texelFetch(image, ivec2(x, clamp(line, 0, uSize.y - 1)), 0).rgb;
  return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

bool combed(float above2, float above, float pixel, float below, float below2) {
  float d1 = pixel - above;
  float d2 = pixel - below;
  return ((d1 > COMB && d2 > COMB) || (d1 < -COMB && d2 < -COMB)) &&
    abs(above2 + 4.0 * pixel + below2 - 3.0 * (above + below)) > 6.0 * COMB;
}

void main() {
  // Block rows count from the top of the frame, as the filter reads them.
  ivec2 block = ivec2(gl_FragCoord.xy);
  ivec2 base = block * ${R};
  float standing = 0.0;
  float woven = 0.0;
  for (int dy = 0; dy < ${R}; ++dy) {
    int y = base.y + dy;
    if (y >= uSize.y || (y & 1) == uFirst) continue;
    for (int dx = 0; dx < ${R}; ++dx) {
      int x = base.x + dx;
      if (x >= uSize.x) break;
      float current = luma(uCur, x, y);
      float previous = luma(uPrev, x, y);
      if (abs(current - previous) <= COMB) continue;
      // The first field's lines either side are the same whichever second
      // field is woven between them.
      float above = luma(uCur, x, y - 1);
      float below = luma(uCur, x, y + 1);
      if (combed(luma(uCur, x, y - 2), above, current, below, luma(uCur, x, y + 2)))
        standing += 1.0;
      if (combed(luma(uPrev, x, y - 2), above, previous, below, luma(uPrev, x, y + 2)))
        woven += 1.0;
    }
  }
  outValue = vec4(standing, woven, 0.0, 0.0);
}
`,xe={prev:"uPrev",cur:"uCur",next:"uNext",size:"uSize",parity:"uParity",tff:"uTff",spatialCheck:"uSpatialCheck",debug:"uDebug",film:"uFilm",second:"uSecond",phase:"uPhase",fieldMetrics:"uFieldMetrics",comb:"uComb"},Ee=`#version 300 es
precision highp float;
precision highp int;

uniform sampler2D uPrev;
uniform sampler2D uCur;
uniform sampler2D uNext;
uniform sampler2D uFieldMetrics;
uniform sampler2D uComb;
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
  return texelFetch(uFieldMetrics, ivec2(metric, 0), 0)[1] <= ${X}.0;
}

/** The pulldown phase the detection gave this frame, or 0. See film-shader.ts. */
int detectedPhase() {
  vec4 phase = texelFetch(uFieldMetrics, ivec2(${d.phase}, 0), 0);
  // Deinterlace each field normally until the cadence is confirmed.
  return phase[1] >= ${I}.0 ? int(phase[0]) : 0;
}

bool isMixedPhase(int phase) {
  return phase == ${U} || phase == ${he};
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
    // A block the weave would leave combed -- a cut, a fade or a telop that
    // does not follow the cadence -- is filtered like video instead.
    vec4 comb = texelFetch(uComb, ivec2(x / ${R}, y / ${R}), 0);
    bool combedBlock = (mixed ? comb[1] : comb[0]) > ${me}.0;
    if ((y & 1) != uParity &&
        (combedBlock || (detectedPhase() == 4 && movingComb(rgb, x, y))))
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
`,w={phase:0,run:0};function L(n,e,t){return Object.fromEntries(Object.entries(t).map(([i,s])=>[i,n.getUniformLocation(e,s)]))}class H{#t;#n;#e;#h;#i;#r;#p;#u;#g;#E=null;#b=null;#a=null;#o=null;#c=0;#f=null;#s=null;#l=0;#U=0;metrics=new Float32Array(F*4);#d=0;#v=0;constructor(e){this.#t=e,this.#n=k(e,le,M),this.#e=L(e,this.#n,ae),this.#h=k(e,ce,M),this.#i=L(e,this.#h,ue),this.#r=k(e,de,M),this.#p=L(e,this.#r,fe),this.#u=k(e,ve,M),this.#g=L(e,this.#u,pe)}get texture(){return this.#o?.[this.#c]?.textures[0]??null}get combTexture(){return this.#a?.textures[0]??null}resize(e,t){e===this.#d&&t===this.#v||(this.#d=e,this.#v=t,this.#_())}reset(){const e=this.#t;e.deleteSync(this.#s),this.#s=null,this.#l=0;const t=this.#o?.[this.#c];if(!t)return;const i=new Float32Array(F*4);for(let s=0;s<d.phase;s++)i[s*4+1]=1;e.bindTexture(e.TEXTURE_2D,t.textures[0]??null),e.texSubImage2D(e.TEXTURE_2D,0,0,0,F,1,e.RGBA,e.FLOAT,i)}detect(e,t,i){const s=this.#t;if(this.#d===0||this.#v===0)return;this.#S();const r=this.#E,o=this.#b,h=this.#o;if(r===null||o===null||h===null)return;const u=h[this.#c],f=h[1-this.#c];if(s.bindFramebuffer(s.FRAMEBUFFER,r.framebuffer),s.useProgram(this.#n),this.#w(0,e,this.#e.a),this.#w(1,t,this.#e.b),this.#w(2,u.textures[0],this.#e.fieldMetrics),s.uniform1i(this.#e.first,i),s.uniform2i(this.#e.size,this.#d,this.#v),s.viewport(0,0,r.width,r.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,o.framebuffer),s.useProgram(this.#h),this.#w(0,r.textures[0],this.#i.second),this.#w(1,r.textures[1],this.#i.first),s.uniform2i(this.#i.size,r.width,r.height),s.viewport(0,0,o.width,o.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,f.framebuffer),s.useProgram(this.#r),this.#w(0,u.textures[0],this.#p.previous),this.#w(1,o.textures[0],this.#p.second),this.#w(2,o.textures[1],this.#p.first),s.uniform2i(this.#p.size,o.width,o.height),s.viewport(0,0,F,1),s.drawArrays(s.TRIANGLES,0,3),this.#c=1-this.#c,this.#l++,this.#s!==null){s.bindFramebuffer(s.FRAMEBUFFER,null);return}this.#U=this.#l,s.bindBuffer(s.PIXEL_PACK_BUFFER,this.#f),s.readPixels(0,0,F,1,s.RGBA,s.FLOAT,0),s.bindBuffer(s.PIXEL_PACK_BUFFER,null),s.bindFramebuffer(s.FRAMEBUFFER,null),this.#s=s.fenceSync(s.SYNC_GPU_COMMANDS_COMPLETE,0),s.flush()}measureComb(e,t,i){const s=this.#t;if(this.#d===0||this.#v===0)return;this.#S();const r=this.#a;r!==null&&(s.bindFramebuffer(s.FRAMEBUFFER,r.framebuffer),s.useProgram(this.#u),this.#w(0,e,this.#g.prev),this.#w(1,t,this.#g.cur),s.uniform1i(this.#g.first,i),s.uniform2i(this.#g.size,this.#d,this.#v),s.viewport(0,0,r.width,r.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,null))}poll(){const e=this.#t,t=this.#s;if(t===null||this.#f===null)return null;switch(e.clientWaitSync(t,0,0)){case e.ALREADY_SIGNALED:case e.CONDITION_SATISFIED:return e.bindBuffer(e.PIXEL_PACK_BUFFER,this.#f),e.getBufferSubData(e.PIXEL_PACK_BUFFER,0,this.metrics),e.bindBuffer(e.PIXEL_PACK_BUFFER,null),e.deleteSync(t),this.#s=null,{phase:this.metrics[d.phase*4]??0,run:this.metrics[d.phase*4+1]??0,age:this.#l-this.#U};default:return null}}destroy(){const e=this.#t;if(this.#_(),this.#o!==null){for(const t of this.#o)P(e,t);this.#o=null}e.deleteSync(this.#s),this.#s=null,e.deleteBuffer(this.#f),this.#f=null,e.deleteProgram(this.#n),e.deleteProgram(this.#h),e.deleteProgram(this.#r),e.deleteProgram(this.#u)}#w(e,t,i){const s=this.#t;s.activeTexture(s.TEXTURE0+e),s.bindTexture(s.TEXTURE_2D,t??null),s.uniform1i(i,e)}#_(){const e=this.#t;this.#E!==null&&P(e,this.#E),this.#b!==null&&P(e,this.#b),this.#a!==null&&P(e,this.#a),this.#E=null,this.#b=null,this.#a=null}#S(){const e=this.#t;if(this.#E===null||this.#b===null||this.#a===null){this.#_();const t=Math.ceil(this.#d/$),i=Math.ceil(this.#v/(V*2));this.#E=D(e,t,i,2),this.#b=D(e,Math.ceil(t/C),Math.ceil(i/C),2),this.#a=D(e,Math.ceil(this.#d/R),Math.ceil(this.#v/R),1)}this.#o===null&&(this.#o=[D(e,F,1,1),D(e,F,1,1)],this.#c=0,this.reset()),this.#f===null&&(this.#f=e.createBuffer(),e.bindBuffer(e.PIXEL_PACK_BUFFER,this.#f),e.bufferData(e.PIXEL_PACK_BUFFER,this.metrics.byteLength,e.STREAM_COPY),e.bindBuffer(e.PIXEL_PACK_BUFFER,null))}}function D(n,e,t,i){const s=n.createFramebuffer();n.bindFramebuffer(n.FRAMEBUFFER,s);const r=[];for(let u=0;u<i;u++){const f=n.createTexture();n.bindTexture(n.TEXTURE_2D,f),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MIN_FILTER,n.NEAREST),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MAG_FILTER,n.NEAREST),n.texImage2D(n.TEXTURE_2D,0,n.RGBA32F,e,t,0,n.RGBA,n.FLOAT,null),n.framebufferTexture2D(n.FRAMEBUFFER,n.COLOR_ATTACHMENT0+u,n.TEXTURE_2D,f,0),r.push(f)}n.drawBuffers(r.map((u,f)=>n.COLOR_ATTACHMENT0+f));const o=n.checkFramebufferStatus(n.FRAMEBUFFER)===n.FRAMEBUFFER_COMPLETE;n.bindFramebuffer(n.FRAMEBUFFER,null);const h={framebuffer:s,textures:r,width:e,height:t};if(!o)throw P(n,h),new Error("failed to allocate framebuffer");return h}function P(n,{framebuffer:e,textures:t}){n.deleteFramebuffer(e);for(const i of t)n.deleteTexture(i)}function _(n,e=0,t=n.length){const i=new DataView(n.buffer,n.byteOffset,n.byteLength),s=[];for(let r=e;r<t;){if(r+8>t)throw new Error("Incomplete MP4 box");const o=i.getUint32(r);if(o<8||r+o>t)throw new Error("Invalid MP4 box size");s.push({type:String.fromCharCode(...n.subarray(r+4,r+8)),start:r,body:r+8,end:r+o}),r+=o}return s}function be(n,e){for(const t of _(n,e.body,e.end).filter(i=>i.type==="trak")){let i=t;for(const s of["mdia","minf","stbl","stsd"]){const r=_(n,i.body,i.end).find(o=>o.type===s);if(!r)break;i=r}if(i.type==="stsd")for(const s of _(n,i.body+8,i.end)){if(s.type!=="avc1")continue;const r=_(n,s.body+78,s.end).find(u=>u.type==="avcC");if(!r)throw new Error("AVC sample entry has no avcC");const o=n.slice(r.body,r.end);return{codec:"avc1."+Array.from(o.subarray(1,4)).map(u=>u.toString(16).padStart(2,"0")).join(""),description:o}}}return null}class ge{#t;#n=null;#e=null;#h=[];#i=0;#r=null;#p=[];#u=new Set;#g=!1;#E=!1;#b=!1;#a=!1;#o=!1;#c=new WeakMap;constructor(e){this.#t=e,e.addEventListener("seeking",this.#s),e.addEventListener("ratechange",this.#s)}get active(){return this.#a}append(e){if(this.#b)return;const t=new Uint8Array(e),i=new DataView(e);try{for(const r of _(t)){if(r.type==="moov"){this.#n=be(t,r);const o=this.#n;o&&VideoDecoder.isConfigSupported(o).then(h=>{this.#c.set(o,h.supported===!0)}).catch(h=>this.#l(h))}if(!(r.type!=="moof"||this.#n===null))for(const o of _(t,r.body,r.end).filter(h=>h.type==="traf")){const h=_(t,o.body,o.end),u=h.find(l=>l.type==="tfhd");if(!u||i.getUint32(u.body+4)!==1)continue;const f=h.find(l=>l.type==="tfdt"),a=h.find(l=>l.type==="trun");if(!f||!a||i.getUint32(f.body)!==16777216||i.getUint32(a.body)!==16781057)throw new Error("Unexpected mpeg2toh264 video fragment layout");let m=Number(i.getBigUint64(f.body+4)),x=r.start+i.getInt32(a.body+8);const c=i.getUint32(a.body+4);if(a.body+12+c*16>a.end)throw new Error("Incomplete video samples");for(let l=0;l<c;l++){const p=a.body+12+l*16,v=i.getUint32(p),E=i.getUint32(p+4),z=i.getUint32(p+8),He=i.getInt32(p+12);if(x<0||x+E>t.length)throw new Error("Video sample outside fragment");this.#h.push({config:this.#n,decodeTime:m/9e4,timestamp:Math.round((m+He)*1e6/9e4),duration:Math.round(v*1e6/9e4),type:z&65536?"delta":"key",data:t.subarray(x,x+E)}),m+=v,x+=E}}}const s=this.#t.buffered;if(s.length>0){let r=0;for(let o=0;o<(this.#a?this.#i:this.#h.length);o++){const h=this.#h[o];h.type==="key"&&h.timestamp/1e6<=s.start(0)&&(r=o)}r>0&&(this.#h.splice(0,r),this.#i=Math.max(0,this.#i-r))}}catch(s){this.#l(s)}}take(){if(this.#b||this.#t.playbackRate<=1.25||this.#n===null||this.#c.get(this.#n)!==!0){this.#a&&this.#s();return}this.#a||(this.#s(),this.#a=!0);const e=this.#t.currentTime;try{for(;this.#i<this.#h.length&&(this.#r?.decodeQueueSize??0)<6&&this.#p.length<12;){const i=this.#h[this.#i];if(i.decodeTime>e+.25)break;if(this.#e!==i.config){if(this.#r){if(!this.#E){this.#E=!0;const r=this.#r;r.flush().then(()=>{this.#r===r&&(r.close(),this.#r=null,this.#e=null,this.#E=!1)}).catch(o=>{this.#r===r&&this.#l(o)})}break}const s=new VideoDecoder({output:r=>{this.#r!==s?r.close():this.#f(r)},error:r=>{this.#r===s&&this.#l(r)}});this.#r=s,this.#r.configure(i.config),this.#e=i.config}(i.duration??0)<1e3&&this.#u.add(i.timestamp),this.#r.decode(new EncodedVideoChunk(i)),this.#i++}if(this.#g&&this.#i===this.#h.length&&this.#r&&!this.#E){this.#E=!0;const i=this.#r;i.flush().catch(s=>{this.#r===i&&this.#l(s)})}}catch(i){this.#l(i);return}const t=this.#p[0];return!t||t.timestamp/1e6>e+.003*this.#t.playbackRate?this.#o?null:void 0:(this.#o=!0,this.#p.shift())}#f=e=>{this.#u.delete(e.timestamp)||e.timestamp/1e6<this.#t.currentTime-(this.#o?.1:.04)?e.close():this.#p.push(e)};#s=()=>{this.#r&&this.#r.state!=="closed"&&this.#r.close(),this.#r=null,this.#e=null;for(const e of this.#p)e.close();this.#p=[],this.#u.clear(),this.#E=!1,this.#a=!1,this.#o=!1,this.#i=0;for(let e=0;e<this.#h.length;e++){const t=this.#h[e];t.type==="key"&&t.timestamp/1e6<=this.#t.currentTime&&(this.#i=e)}};finish(){this.#g=!0}suspend(){this.#s()}reset(){this.#s(),this.#h=[],this.#i=0,this.#n=null,this.#g=!1,this.#b=!1}destroy(){this.reset(),this.#t.removeEventListener("seeking",this.#s),this.#t.removeEventListener("ratechange",this.#s)}#l(e){this.#s(),this.#b=!0,console.warn("mpeg2toh264: decoded video input unavailable",e)}}const W=["mozParsedFrames","mozDecodedFrames","mozPresentedFrames","mozPaintedFrames"];function ye(n){return W.every(e=>e in n)}function Te(n){return n.ownerDocument?.defaultView?.performance.timeOrigin??performance.timeOrigin}const Fe=250,Re=500;class we{#t;#n;#e;#h=null;#i=null;#r=null;#p=null;#u=!0;#g=null;#E=null;#b=0;#a;#o;#c=null;#f=null;#s=null;#l=null;#U=0;#d=[];#v=[];constructor(e,t){if(this.#t=e,this.#n=t,this.#e=ye(e)?e:null,this.#a=this.#e===null&&typeof VideoFrame<"u",this.#o=this.#a&&e.playbackRate>1,this.#e){for(const i of["emptied","seeking","seeked"])e.addEventListener(i,this.#B);for(const i of["pause","playing","waiting","ratechange"])e.addEventListener(i,this.#z)}if(this.#a)for(const i of["loadeddata","playing","pause","ended","seeking","seeked","emptied","ratechange"])e.addEventListener(i,this.#_)}get captureDriven(){return this.#o}request(e){if(this.#i===null){if(this.#i=e,this.#o){this.#S();return}this.#h=this.#e?requestAnimationFrame(this.#ie):this.#t.requestVideoFrameCallback(this.#C)}}cancel(){this.#h!==null&&(this.#e?cancelAnimationFrame(this.#h):this.#t.cancelVideoFrameCallback(this.#h)),this.#h=null,this.#i=null,this.#c?.(),this.#c=null,this.#s!==null&&this.#t.cancelVideoFrameCallback(this.#s),this.#s=null,this.#w(),this.#l=null,this.#d=[],this.#o=this.#a&&this.#t.playbackRate>1,this.#B()}destroy(){this.cancel();for(const e of["emptied","seeking","seeked"])this.#t.removeEventListener(e,this.#B);for(const e of["pause","playing","waiting","ratechange"])this.#t.removeEventListener(e,this.#z);for(const e of["loadeddata","playing","pause","ended","seeking","seeked","emptied","ratechange"])this.#t.removeEventListener(e,this.#_)}flush(e){if(this.#o)for(this.#t.ownerDocument!==this.#f&&(this.#c?.(),this.#c=null,this.#S());this.#v.length>0&&this.#i!==null;){const t=this.#v.shift(),i=t.frame;try{this.#I(e,{width:i.visibleRect?.width??i.codedWidth,height:i.visibleRect?.height??i.codedHeight,mediaTime:i.timestamp/1e6,presentedFrames:t.count,expectedDisplayTime:Math.max(t.at,e),timeOrigin:performance.timeOrigin,frame:i})}finally{i.close()}}}#w(){for(const e of this.#v)e.frame.close();this.#v=[]}#_=e=>{const t=this.#a&&this.#t.playbackRate>1;if(t!==this.#o){const i=this.#i;this.cancel(),this.#o=t,i!==null&&this.request(i);return}["seeking","seeked","emptied","ratechange"].includes(e.type)&&(this.#l=null,this.#d=[]),this.#o&&((e.type==="pause"||e.type==="ended")&&this.flush(performance.now()),this.#w(),this.#c?.(),this.#c=null,this.#i!==null&&this.#S())};#S(){if(!this.#o||this.#c!==null||this.#i===null||(this.#t.paused||this.#t.ended)&&this.#l!==null)return;this.#s===null&&typeof this.#t.requestVideoFrameCallback=="function"&&(this.#s=this.#t.requestVideoFrameCallback(this.#Be));const e=Math.max(4,8/Math.max(1,this.#t.playbackRate)),t=this.#t.ownerDocument?.defaultView;if(this.#f=this.#t.ownerDocument,t){const i=t.setTimeout(this.#J,e);this.#c=()=>t.clearTimeout(i)}else{const i=setTimeout(this.#J,e);this.#c=()=>clearTimeout(i)}}#Be=()=>{this.#s=null,this.#c?.(),this.#c=null,this.#J()};#J=()=>{this.#c=null;const e=this.#t;if(this.#i===null)return;if(e.readyState<2||e.seeking){this.#S();return}let t,i=!1;try{const s=this.#n?.();if(s===null){this.#S();return}i=s!==void 0,t=s??new VideoFrame(e)}catch(s){if(!(s instanceof DOMException)||s.name!=="InvalidStateError")throw s;this.#S();return}if(t.timestamp===this.#l)t.close();else{let s=1;if(this.#l!==null){const o=t.timestamp-this.#l;if(o>1e3&&o<25e4&&(this.#d.push(o),this.#d.length>7&&this.#d.shift()),o>0&&this.#d.length>0){const h=[...this.#d].sort((f,a)=>f-a),u=h[Math.floor(h.length/2)];s=Math.max(1,Math.round(o/u))}}this.#l=t.timestamp,this.#U+=s;const r=performance.now()+(i?(t.timestamp/1e6-e.currentTime)*1e3/e.playbackRate:0);for(this.#v.push({frame:t,at:r,count:this.#U});this.#v.length>4;)this.#v.shift().frame.close()}this.#S()};#z=()=>{this.#g=null,this.#E=null,this.#b=0};#B=()=>{this.#r=null,this.#p=null,this.#u=!0,this.#z()};#C=(e,t)=>{this.#I(e,{width:t.width,height:t.height,mediaTime:t.mediaTime,presentedFrames:t.presentedFrames,expectedDisplayTime:t.expectedDisplayTime,timeOrigin:Te(this.#t)})};#I=(e,t)=>{const i=this.#i;this.#h=null,this.#i=null,i?.(e,t)};#ie=e=>{const t=this.#e,i=W.map(h=>t[h]);this.#r?.some((h,u)=>i[u]<h)&&this.#B(),this.#r=i;const s=t.mozPaintedFrames,r=!t.seeking&&t.readyState>=2&&t.videoWidth>0&&t.videoHeight>0,o=this.#p===null&&(s>0||t.paused&&(t.mozPresentedFrames>0||t.mozDecodedFrames>0));if(r&&(o||this.#p!==null&&s!==this.#p)){if(this.#g!==null&&e-this.#g>Re&&(this.#z(),this.#u=!0),!t.paused&&!t.ended){const u=this.#E;if(u&&e-u.at>=Fe){const f=s-u.frames;if(f>0){const a=(e-u.at)/f;a>=4&&a<=200&&(this.#b=this.#b?this.#b+(a-this.#b)*.25:a)}this.#E=null}this.#E??={at:e,frames:s}}this.#g=e,this.#p=s;const h=this.#u;this.#u=!1,this.#I(e,{width:t.videoWidth,height:t.videoHeight,mediaTime:t.currentTime,presentedFrames:s,expectedDisplayTime:e,timeOrigin:performance.timeOrigin,mozTiming:{periodMs:this.#b,discontinuity:h}})}else this.#h=requestAnimationFrame(this.#ie)}}let _e=null;const q=.5,y=4,O=5,A=O+1,K=1e3,Q=4,B=200,Ae=.25,Se=1e3/60,ke=`#version 300 es
void main() {
  // One triangle over the whole viewport, from the vertex index alone. There
  // is no geometry here worth a buffer: every pixel is the fragment shader's.
  vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
`,Ce=.75,De=.1,j=1,Pe=.02,Me=.1,Y=1,Le=4,N=5,Be=4,Ue={2:0,3:.25,4:.5,5:.75},Ie=`#version 300 es
precision highp float;
uniform sampler2D uField;
uniform bool uFlip;
out vec4 fragColor;
void main() {
  ivec2 position = ivec2(gl_FragCoord.xy);
  if (uFlip) position.y = textureSize(uField, 0).y - 1 - position.y;
  fragColor = texelFetch(uField, position, 0);
}
`,Oe={requestAnimationFrame:n=>requestAnimationFrame(n),cancelAnimationFrame:n=>cancelAnimationFrame(n)};class Ne extends EventTarget{encodedVideo;#t;#n;#e;#h;#i;#r=null;#p;#u;#g;#E;#b;#a=[];#o=[];#c=A-1;#f=null;#s=[];#l=null;#U=0;#d=null;#v=null;#w;#_=Se;#S=0;#Be=0;#J=0;#z=0;#B=null;#C(){this.#s.length=0,this.#B=null,this.#z=0}#I=null;#ie;#O;#se;#re=0;#G;#k;#T=0;#M=0;#X=0;#L=y-1;#F=0;#ge=0;#Qe=0;#ye=!1;#R=!1;#Z=0;#Ue=!1;#$=!1;#y=null;#ne=[];#N=!1;#je;#Ye;#A;#oe;#H;#Je;#m=null;#x;#Te=!1;#Ze=0;#et=!1;#Vt=0;#Fe=!1;#Ie=!1;#he=null;#Ht=0;#Re=new Map;#D={filtered:0,missed:0,degraded:0,discontinuities:0,resynced:0,late:0,queueResetted:0};#we=0;#Oe=0;#Ne=0;#W=0;#ae=0;#le=0;#_e=0;#ue=0;#ce;#ze=[];#fe=[];#Ae=0;#de=0;#Se=0;#me=0;#ke=w;#pe=0;#P=w;#q=!1;#ve=null;#Et="";#Ge=[0,0,0,0,0,0];#tt=0;#ee=null;#it=null;#st=0;constructor(e,t={},i=null){super(),this.#e=e,this.#O=t.doubleRate??!1,this.#se=t.spatialCheck??!0,this.#G=t.debug??!1,this.#k=t.film??!1,this.#je=t.onStats,this.#Ye=t.onFailure,this.#A=i,this.#H=i?"main":t.rendering??"main",this.#Je=t.workerUrl??_e,this.#x=this.#H==="main"?"main":"idle",this.#n=i?i.canvas:document.createElement("canvas"),this.#t=i?.canvas??(this.#H==="main"?this.#n:document.createElement("canvas")),this.#oe=e,i||(this.#n.style.cssText="position:absolute;pointer-events:none;visibility:hidden");const s=this.#t.getContext("webgl2",{alpha:!0,antialias:!1,depth:!1,stencil:!1,preserveDrawingBuffer:!1,powerPreference:"high-performance"});if(!(s instanceof WebGL2RenderingContext))throw new Error("this browser has no WebGL2");this.#i=s,this.#k&&(this.#Tt(),this.#r=new H(s)),this.#p=J(s,Ee);const r=this.#p;this.#u=Object.fromEntries(Object.entries(xe).map(([o,h])=>[o,s.getUniformLocation(r,h)])),this.#g=J(s,Ie),this.#E=s.getUniformLocation(this.#g,"uField"),this.#b=s.getUniformLocation(this.#g,"uFlip"),this.#ce=s.getExtension("EXT_disjoint_timer_query_webgl2"),this.#t.addEventListener("webglcontextlost",this.#$t),this.#ie=i?null:new ResizeObserver(()=>this.#Me()),this.#w=i?null:new MutationObserver(()=>{this.#n.ownerDocument!==this.#v&&this.#Me()}),this.encodedVideo=!i&&typeof VideoDecoder<"u"?new ge(e):null,this.#h=new we(e,()=>this.encodedVideo?.take()),e.addEventListener("emptied",this.#zt),e.addEventListener("resize",this.#Nt),e.addEventListener("pause",this.#Y),e.addEventListener("ended",this.#Y),e.addEventListener("seeking",this.#Xt),e.addEventListener("seeked",this.#Y),e.addEventListener("ratechange",this.#Y)}get running(){return this.#R&&(this.#y?.interlaced??!0)}get canvas(){return this.#n}get#bt(){return this.#y?.topFieldFirst!==!1}#gt(){return{doubleRate:this.#O,spatialCheck:this.#se,film:this.#k,debug:this.#G}}get enabled(){return this.#Ue}set enabled(e){this.#Ue=e,this.#rt(),this.#m?.postMessage({type:"enabled",enabled:e})}set scan(e){const t=this.#y?.interlaced!==e?.interlaced,i=t||this.#y?.topFieldFirst!==e?.topFieldFirst;this.#y=e,!(i&&(!this.#Ee()||this.#y!==e))&&(this.#m?.postMessage({type:"scan",scan:e}),i&&(this.#F=0,this.#C(),this.#V(),t&&(this.#T=0),this.#f=null,this.#j(!1)),this.#rt(),i&&((e?.interlaced??!0)&&(this.#A||this.#x==="main")?this.#Pe():this.#ct()))}get scan(){return this.#y}set videoTimeline(e){this.#ne=e,this.#m?.postMessage({type:"timeline",videoTimeline:e}),e.length===0&&(this.#y=null),this.#rt()}get videoTimeline(){return this.#ne}get container(){return this.#I??this.#e}get doubleRate(){return this.#O}set doubleRate(e){e!==this.#O&&(this.#O=e,this.#xe(),this.#C(),this.#yt())}get spatialCheck(){return this.#se}set spatialCheck(e){e!==this.#se&&(this.#se=e,this.#xe())}get film(){return this.#k}set film(e){const t=this.#m?this.#it:this.#ee;if(!(e===this.#k&&(e===!1||t===null))){if(this.#m){this.#k=e,this.#xe(e?"film":void 0);return}if(e){if(!this.#Ee())return;try{this.#Ft()}catch(i){this.#k=!0,this.#xe(),this.#ot(`film detector unavailable: ${i instanceof Error?i.message:String(i)}`);return}}if(this.#k=e,this.#xe(),!e){if(!this.#Ee())return;this.#q=!1,this.#P=w,this.#V(),this.#r?.destroy(),this.#r=null}this.#yt()}}get debug(){return this.#G}set debug(e){e!==this.#G&&(this.#G=e,this.#xe())}get#Wt(){return this.#O||this.#k}#yt(){this.#$||(this.#Wt?(this.#M>0&&this.#Ot(),(this.#y?.interlaced??!0)&&(this.#A||this.#x==="main")&&this.#Pe()):this.#k||(this.#f=null,this.#j(!1),this.#Le()))}#xe(e){this.#m?.postMessage({type:"settings",options:this.#gt(),retryFilm:e})}#Tt(){if(this.#i.getExtension("EXT_color_buffer_float")===null)throw new Error("film needs EXT_color_buffer_float")}#Ft(){this.#Tt(),this.#r??=new H(this.#i),this.#M>0&&this.#r.resize(this.#M,this.#X)}#rt(){this.#Ue&&(this.#ne.length>0||(this.#y?.interlaced??!0))?this.start():this.stop()}#qt(){return this.#A||this.#H==="main"?!1:this.#x==="starting"||this.#x==="active"?!0:typeof Worker<"u"&&typeof VideoFrame<"u"&&typeof OffscreenCanvas<"u"&&this.#Je!==null&&"transferControlToOffscreen"in HTMLCanvasElement.prototype?(this.#Rt(),!0):this.#H==="auto"?(this.#Xe(),!1):(this.#x="failed",this.#R=!1,!0)}#Rt(){this.#K(),this.#m?.terminate(),this.#m=null,this.#Fe=!1,this.#Ie=!1,this.#it=null,this.#st=0;let e=this.#n;if(this.#et){e=document.createElement("canvas"),e.className=this.#n.className;const r=this.#n.getAttribute("style");r===null?e.removeAttribute("style"):e.setAttribute("style",r),e.style.visibility="hidden",this.#n.parentElement&&this.#n.replaceWith(e),this.#n=e}const t=++this.#Ze;this.#x="starting";let i,s;try{s=e.transferControlToOffscreen(),this.#et=!0,i=new Worker(this.#Je,{type:"module"})}catch(r){this.#Ce(r instanceof Error?r.message:String(r));return}this.#m=i,i.onmessage=r=>{t===this.#Ze&&this.#Kt(r.data)},i.onerror=r=>{t===this.#Ze&&(r.preventDefault(),this.#Ce(r.message||"the deinterlacer worker failed"))},i.postMessage({type:"initialize",canvas:s,options:this.#gt(),scan:this.#y,videoTimeline:this.#ne,enabled:this.#R,video:this.#ht()},[s])}#Kt(e){switch(e.type){case"ready":this.#x="active",this.#R&&(this.#De(),this.#Ke());break;case"failed":this.#Ce(e.message);break;case"consumed":{this.#Fe=!1,this.#Ie=!0;const t=this.#he;this.#he=null,t&&this.#_t(t);break}case"visibility":this.#n.style.visibility=e.visible?"visible":"hidden";break;case"stats":{const t={...e.stats,dropped:this.#e.getVideoPlaybackQuality?.().droppedVideoFrames??0},i=t.filmError??null,s=this.#st;if(this.#it=i,this.#st=e.filmFailure,i!==null&&e.filmFailure!==s){this.dispatchEvent(new CustomEvent("failure",{detail:i}));try{this.#Ye?.(i)}catch{}}this.dispatchEvent(new CustomEvent("stats",{detail:t})),this.#je?.(t);break}case"capture":{const t=this.#Re.get(e.id);if(this.#Re.delete(e.id),!t){e.image?.close();break}e.image?t.resolve(e.image):createImageBitmap(this.#e).then(t.resolve,t.reject);break}}}#nt(e){if(this.dispatchEvent(new CustomEvent("failure",{detail:e})),!this.#A)try{this.#Ye?.(e)}catch{}}#ot(e){this.#ee!==e&&(this.#ee=e,this.#q=!1,this.#P=w,this.#V(),this.#r?.destroy(),this.#r=null,this.#nt(e))}#Ee(){return this.#$?!1:(this.#m||(this.#ee=null),!0)}#Ce(e){if(this.#x==="starting"&&this.#H==="auto"&&!this.#Te){this.#Xe();return}if(this.#wt(e),!this.#Te){this.#Te=!0,this.#Rt();return}console.error(`Deinterlacer Worker stopped: ${e}`),this.#x="failed",this.#m?.terminate(),this.#m=null,this.#K(),this.#nt(`deinterlacer worker stopped: ${e}`),this.stop()}#Xe(){const e=this.#t;e.className=this.#n.className;const t=this.#n.getAttribute("style");t===null?e.removeAttribute("style"):e.setAttribute("style",t),e.style.visibility="hidden",this.#n.parentElement&&this.#n.replaceWith(e),this.#n=e,this.#et=!1,this.#m?.terminate(),this.#m=null,this.#x="main",this.#K(),this.#R&&(this.#De(),this.#Ke(),(this.#y?.interlaced??!0)&&this.#Pe())}#K(){this.#he?.frame.close(),this.#he=null}#wt(e){for(const t of this.#Re.values())t.reject(new Error(e));this.#Re.clear()}start(){if(!(this.#R||this.#$||this.#N)&&(this.#Z++,this.#R=!0,this.#Gt(),!!this.#Ee())){if(this.#ui(),this.#Ke(),this.#qt()){this.#m?.postMessage({type:"enabled",enabled:!0}),this.#x==="active"&&this.#De();return}this.#De(),(this.#y?.interlaced??!0)&&this.#Pe()}}stop(){this.#Z++,this.#R&&(this.#R=!1,this.#h.cancel(),this.encodedVideo?.suspend(),this.#Dt(),this.#ct(),this.#F=0,this.#f=null,this.#j(!1),this.#K(),this.#m?.postMessage({type:"enabled",enabled:!1}))}destroy(){if(!this.#$){this.#$=!0,this.#Ue=!1,this.stop(),this.#m?.postMessage({type:"destroy"}),this.#m?.terminate(),this.#m=null,this.#K(),this.#wt("the deinterlacer was destroyed"),this.#v?.removeEventListener("visibilitychange",this.#mt),this.#v=null,this.#w?.disconnect(),this.#t.removeEventListener("webglcontextlost",this.#$t),this.#h.destroy(),this.encodedVideo?.destroy(),this.#e.removeEventListener("emptied",this.#zt),this.#e.removeEventListener("resize",this.#Nt),this.#e.removeEventListener("pause",this.#Y),this.#e.removeEventListener("ended",this.#Y),this.#e.removeEventListener("seeking",this.#Xt),this.#e.removeEventListener("seeked",this.#Y),this.#e.removeEventListener("ratechange",this.#Y),this.#ci();for(const e of this.#a)this.#i.deleteTexture(e);this.#a=[],this.#Le();for(const e of[...this.#ze,...this.#fe.map(({q:t})=>t)])this.#i.deleteQuery(e);this.#ze.length=0,this.#fe.length=0,this.#r?.destroy(),this.#r=null,this.#ve!==null&&(ne(this.#ve),this.#ve=null),this.#i.deleteProgram(this.#p),this.#i.deleteProgram(this.#g),this.#i.getExtension("WEBGL_lose_context")?.loseContext()}}capture(){if(this.#x==="active"&&this.#n.style.visibility==="visible"&&this.#m){const s=++this.#Ht,r=new Promise((o,h)=>{this.#Re.set(s,{resolve:o,reject:h})});return this.#m.postMessage({type:"capture",id:s,width:this.#e.videoWidth,height:this.#e.videoHeight}),r}if(this.#x==="starting"||this.#x==="failed")return createImageBitmap(this.#e);const e=this.#f;if(this.#A&&(!this.#R||this.#N||!e))return Promise.reject(new Error("no rendered picture is available"));if(!this.#R||this.#N||!e)return createImageBitmap(this.#e);e.kind==="texture"?this.#vt(e.texture,e.flip,!1):this.#te(e.flush,e.second,null,!1);const t=this.#e.videoWidth,i=this.#e.videoHeight;return t>0&&i>0&&(t!==this.#t.width||i!==this.#t.height)?createImageBitmap(this.#t,{resizeWidth:t,resizeHeight:i,resizeQuality:"high"}):createImageBitmap(this.#t)}addEventListener(e,t,i){super.addEventListener(e,t,i)}removeEventListener(e,t,i){super.removeEventListener(e,t,i)}#De(){this.#A||!this.#R||this.#h.request(this.#ti)}#ht(){const e=[];for(let t=0;t<this.#e.buffered.length;t++)e.push({start:this.#e.buffered.start(t),end:this.#e.buffered.end(t)});return{currentTime:this.#e.currentTime,playbackRate:this.#e.playbackRate,seeking:this.#e.seeking,paused:this.#e.paused,ended:this.#e.ended,readyState:this.#e.readyState,videoWidth:this.#e.videoWidth,videoHeight:this.#e.videoHeight,buffered:e}}#Qt(e,t,i){let s;try{s=i?.clone()??new VideoFrame(this.#e,{timestamp:Math.max(0,Math.round(t.mediaTime*1e6))})}catch(o){const h=o instanceof Error?o.message:String(o);this.#H==="auto"&&!this.#Ie&&!this.#Te?(this.#Xe(),this.#Ve(e,t)):this.#Ce(h);return}const r={id:++this.#Vt,frame:s,now:e,metadata:t,video:this.#ht()};if(this.#Fe){this.#he?.frame.close(),this.#he=r;return}this.#_t(r)}#_t(e){const t=this.#m;if(!t||this.#x!=="active"){e.frame.close();return}this.#Fe=!0;const i={type:"frame",id:e.id,frame:e.frame,metadata:e.metadata,video:e.video};try{t.postMessage(i,[e.frame])}catch(s){this.#Fe=!1,e.frame.close();const r=s instanceof Error?s.message:String(s);this.#H==="auto"&&!this.#Ie&&!this.#Te?(this.#Xe(),this.#Ve(e.now,e.metadata)):this.#Ce(r)}}#jt(e,t,i){this.#ve==null&&(this.#ve=se(this.#i,"20px monospace")),oe(this.#ve,e,t,i,this.#M,this.#X,20)}#At(e){if(this.#ce==null||this.#fe.length>30)return;const t=this.#ze.pop()??this.#i.createQuery();return this.#i.beginQuery(this.#ce.TIME_ELAPSED_EXT,t),this.#fe.push({q:t,isField:e}),t}#$e(e){this.#ce!=null&&(e!=null&&this.#i.endQuery(this.#ce.TIME_ELAPSED_EXT),this.#fe=this.#fe.filter(({q:t,isField:i})=>{if(this.#i.getQueryParameter(t,this.#i.QUERY_RESULT_AVAILABLE)){const s=this.#i.getQueryParameter(t,this.#i.QUERY_RESULT);return i?(this.#Se+=s,this.#me++):(this.#Ae+=s,this.#de++),this.#ze.push(t),!1}return!0}))}#V(){this.#P=w,this.#ke=w,this.#pe=0,this.#q=!1,this.#r?.reset()}#Yt(){const{prev:e,cur:t,next:i}=this.#Ut(!1),s=this.#a[e],r=this.#a[t],o=this.#a[i];if(!s||!r||!o)return;const h=this.#y?.topFieldFirst!==!1?0:1;this.#r?.detect(r,o,h),this.#r?.measureComb(s,r,h)}#Jt(){const e=this.#r?.poll()??null;e!==null&&(this.#ke=e,this.#pe=e.age),this.#pe++;const{phase:t,run:i}=this.#ke;t===0||this.#pe>Math.ceil(N*Math.max(1,this.#e.playbackRate))?this.#P=w:this.#P={phase:(t-1+this.#pe)%N+1,run:i}}#Zt(e){const t=[],i=this.#r?.metrics??new Float32Array(0);for(let r=0;r<d.phase;r++){const o=i[r*4]??0,h=i[r*4+1]??0,u=i[r*4+2]??0;t.push(`${o.toFixed(3)},${h.toString().padStart(4)},${u.toFixed(3)}`)}const s=this.#Ge.map((r,o)=>`${o===0?"-":o}:${r}`).join(" ");return`frame=${e} phase=${this.#P.phase} run=${this.#P.run} known=${this.#ke.phase}/${this.#ke.run} age=${this.#pe} ${this.#q?"film":"video"} period=${this.#T.toFixed(3)}
${t.join(" ")}
${s} dropped:${this.#tt}`}#at(e,t){const i=t-performance.timeOrigin;return Number.isFinite(i)&&i!==0?e+i:e}#ei(e,t){const i=e.expectedDisplayTime;if(!Number.isFinite(i)||i<=0||!Number.isFinite(e.timeOrigin))return t;const s=this.#at(i,e.timeOrigin),r=Le*Math.max(this.#_,this.#T);return s<t-r||s>t+r?t:s}#ti=(e,t)=>{if(!this.#R||this.#N)return;this.#dt();const i=this.#at(e,t.timeOrigin),{frame:s,...r}=t;this.#oe=s??this.#e;try{this.#ii(i,r,s)}finally{this.#oe=this.#e}this.#De()};#ii(e,t,i){if(this.#x==="active"){this.#Qt(e,t,i);return}this.#x!=="starting"&&this.#Ve(e,t)}ingestExternalFrame(e,t,i){this.#oe=i;try{this.#Ve(e,t)}finally{this.#oe=this.#e}}#Ve(e,t){const i=this.#Z;if(this.#Q(i)&&(this.#si(t.mediaTime),!!this.#Q(i)&&t.width>0&&t.height>0)){let s=!1;if(!this.#ye&&this.#e.seeking){const l=this.#e.buffered,p=this.#T>=Q?this.#T/1e3:B/1e3;for(let v=0;v<l.length;v++)if(t.mediaTime>=l.start(v)&&t.mediaTime<l.end(v)&&Math.abs(t.mediaTime-this.#e.currentTime)<=p){s=!0;break}}if(s&&(this.#ye=!0),(this.#M===0||this.#X===0)&&this.#It(t.width,t.height),!this.#Q(i))return;if(this.#y&&!this.#y.interlaced){const l=performance.now();this.#Mt(l),this.#Oe=l,this.#ai(),this.#ae+=performance.now()-l,this.#W++,this.#le++,this.#Lt(l);return}const r=t.mediaTime-this.#ge,o=t.mozTiming,h=s||(o?o.discontinuity||r<0||r>q:r<0||r>q);h&&(this.#F=0,this.#T=0,this.#D.discontinuities++,this.#C(),this.#V());const u=this.#li(t.presentedFrames,h);if(this.#F>0&&t.mediaTime===this.#ge&&(!o||t.presentedFrames===this.#Qe))return;if(!h){const l=o?.periodMs??0;l>0?this.#St(l*(this.#e.playbackRate||1)/1e3,1):this.#F>0&&r>0&&this.#St(r,u+1)}this.#ge=t.mediaTime,this.#Qe=t.presentedFrames;const f=performance.now();this.#Mt(f),this.#Oe=f;const a=performance.now(),m=this.#At(!1);if(this.#Bt(),this.#k&&!this.#ee&&!this.#r)try{this.#Ft()}catch(l){this.#ot(`film detector unavailable: ${l instanceof Error?l.message:String(l)}`)}if(!this.#Q(i)){this.#$||this.#$e(m);return}if(this.#k&&!this.#ee){if(this.#F===y&&u===0)try{this.#Jt(),this.#Yt()}catch(l){this.#ot(`film detection failed: ${l instanceof Error?l.message:String(l)}`)}else this.#V();this.#Ge[this.#P.phase]=(this.#Ge[this.#P.phase]??0)+1,this.#q=this.#P.phase!==0&&this.#P.run>=I,this.#G&&(this.#Et=this.#Zt(t.presentedFrames))}if(!this.#Q(i)){this.#$||this.#$e(m);return}const c=this.#ei(t,e)+this.#_;if(this.#q)if(this.#He()){const l=this.#P.phase;if(l===U)this.#tt++,this.#z++;else{const p=this.#T*N/Be,v=this.#ut(1,e,p),E=Ue[l]??0,z=v||this.#B===null?c+p:c+E*this.#T;this.#We("film",!1,this.#lt("film",z,p),p)}}else this.#te(!1,!1,null);else if(this.#O&&this.#He()){const l=this.#T/2,v=this.#ut(2,e,l)||this.#B===null?c+l*2:c,E=this.#lt("field",v,l);this.#We("field",!1,E,l),this.#We("field",!0,E+l,l)}else if(this.#He()){const l=this.#T,v=this.#ut(1,e,l)||this.#B===null?c+l:c;this.#We("frame",!1,this.#lt("frame",v,l),l)||(this.#D.late++,this.#te(!1,!1,null))}else this.#D.late+=this.#s.length,this.#C(),this.#te(!1,!1,null);this.#ue=Math.max(this.#ue,this.#s.length),this.#$e(m),this.#ae+=performance.now()-a,this.#W++,this.#Lt(f)}}#Q(e){return!this.#$&&this.#R&&e===this.#Z}#si(e){const t=this.#Z;let i;for(let o=this.#ne.length-1;o>=0;o--){const h=this.#ne[o];if(h.start<=e+1e-6){i=h;break}}if(i?.codedSize&&(i.codedSize.width!==this.#M||i.codedSize.height!==this.#X)&&this.#It(i.codedSize.width,i.codedSize.height),!this.#Q(t))return;const s=i?.scan;if(!s||this.#y?.interlaced===s.interlaced&&this.#y.topFieldFirst===s.topFieldFirst)return;const r=this.#y?.interlaced;this.#y=s,this.#F=0,this.#C(),this.#Ee()&&(r!==s.interlaced&&(this.#T=0),s.interlaced&&(this.#A||this.#x==="main")?this.#Pe():this.#ct(),this.#V())}#He(){return(this.#O||this.#k)&&this.#T>0&&this.#o.length===A}#St(e,t){const s=e*1e3/(this.#e.playbackRate||1)/t;s<Q||s>B||(this.#T=this.#T>0&&s>this.#T*Ce?this.#T+(s-this.#T)*Ae:s)}#We(e,t,i,s){const r=this.#kt();if(r===null)return!1;const o=this.#o[r];if(!o)return!1;for(this.#c=r;this.#s.length>0&&this.#s[0]?.slot===r;)this.#s.shift(),this.#D.late++;this.#te(!1,t,o.framebuffer);const h={slot:r,at:i,duration:s,cadence:e,phase:e==="film"?this.#P.phase:e==="field"?t?2:1:0,droppedBefore:this.#z};return this.#z=0,this.#s.push(h),this.#B=h,!0}#lt(e,t,i){if(!(i>0))return t;const s=this.#B;if(s!==null&&s.cadence===e){const r=s.at+s.duration,o=t-r;if(Math.abs(o)<i){const h=Math.max(-j,Math.min(j,o*De));return r+h}}s!==null&&this.#D.resynced++;for(let r=this.#s.at(-1);r&&r.at>=t;)this.#s.pop(),this.#D.late++,r=this.#s.at(-1);return t}#ut(e,t,i){const s=this.#s.at(-1),r=(O+1)*Math.max(this.#_,i);if(s&&s.at-t>r)return this.#C(),this.#D.queueResetted++,!0;const o=Math.max(0,this.#s.length+e-O);let h=0,u=0;for(;u<o;){const f=this.#s.shift();if(!f)break;h+=f.duration,u++}for(const f of this.#s)f.at-=h;return this.#D.late+=u,!1}#kt(){const e=this.#f?.kind==="texture"?this.#f.texture:null,t=new Set(this.#s.map(({slot:s})=>s));for(let s=1;s<=A;s++){const r=(this.#c+s)%A,o=this.#o[r];if(o&&o.texture!==e&&!t.has(r))return r}const i=this.#s[0];if(i){const s=this.#o[i.slot];if(s&&s.texture!==e)return i.slot}return null}#Pe(){this.#l===null&&(!this.#R||this.#N||(this.#U=0,this.#l=this.#be(this.#ft)))}#ct(){this.#qe(this.#l),this.#l=null,this.#C()}#ft=e=>{if(this.#l=null,!this.#R||this.#N)return;this.#ri(e);const t=this.#Z;this.#h.flush(e),this.#Q(t)&&(this.#x==="main"&&this.#oi(this.#S,e),this.#l=this.#be(this.#ft))};#ri(e){const t=e-this.#U;this.#U=e;const i=Math.max(1,Math.round(t/this.#_)),s=this.#S+i*this.#_,r=e-s;if(this.#S===0||t<=0||t>B||Math.abs(r)>this.#_/4){t>=1&&t<=B&&(this.#_=t),this.#S=e;return}this.#_+=r/i*Pe,this.#S=s+r*Me}#Ct(){const e=this.#A;if(e)return{frames:e,origin:performance.timeOrigin};const t=this.#n.ownerDocument?.defaultView??this.#e.ownerDocument?.defaultView??null;return t===null?{frames:Oe,origin:performance.timeOrigin}:{frames:t,origin:t.performance.timeOrigin}}#be(e){const{frames:t,origin:i}=this.#Ct(),s=t.requestAnimationFrame(r=>e(this.#at(r,i)));return{frames:t,handle:s}}#qe(e){e?.frames.cancelAnimationFrame(e.handle)}#dt(){if(this.#A)return;this.#ni();const{frames:e}=this.#Ct(),t=this.#l!==null&&this.#l.frames!==e,i=this.#d!==null&&this.#d.frames!==e;!t&&!i||(this.#U=0,t&&(this.#qe(this.#l),this.#l=this.#be(this.#ft)),i&&(this.#qe(this.#d),this.#d=this.#be(this.#pt)))}#ni(){const e=this.#A?null:this.#n.ownerDocument??null;e!==this.#v&&(this.#v?.removeEventListener("visibilitychange",this.#mt),this.#v=e,e?.addEventListener("visibilitychange",this.#mt),this.#w?.disconnect(),e&&this.#w?.observe(e,{childList:!0,subtree:!0}))}#mt=()=>{this.#$||this.#dt()};#Ke(){this.#A||this.#d!==null||!this.#h.captureDriven||!this.#R||this.#N||(this.#d=this.#be(this.#pt))}#Dt(){this.#qe(this.#d),this.#d=null}#pt=e=>{if(this.#d=null,!this.#R||this.#N)return;const t=this.#Z;this.#h.flush(e),this.#Q(t)&&this.#h.captureDriven&&(this.#d=this.#be(this.#pt))};#oi(e,t){const i=this.#_/2,s=u=>{const f=u.at-e;return f<=i-Y?!0:f>i+Y?!1:this.#Be>0};for(;this.#s[1]&&s(this.#s[1]);)this.#D.late++,this.#s.shift();const r=this.#s[0];if(!r||!s(r))return;this.#s.shift(),this.#Be=r.at-e;const o=performance.now(),h=this.#At(!0);this.#Pt(r.slot),this.#$e(h),this.#_e+=performance.now()-o,this.#le++,this.#G&&this.#hi(r,t),this.#J=t}#hi(e,t){const i=this.#J===0?0:t-this.#J,s=i/this.#_,r=e.cadence==="film"?`phase ${e.phase}`:e.cadence==="field"?`field ${e.phase}`:"frame",o=e.phase===0?"duplicate":`phase ${U}`,h=e.droppedBefore>0?`, ${o} dropped before it`+(e.droppedBefore>1?` (${e.droppedBefore})`:""):"";console.log(`yadif: +${i.toFixed(2)} ms (${s.toFixed(2)} refreshes) ${e.cadence} ${r}, due ${(e.at-t).toFixed(2)} ms${h}`)}#Pt(e){const t=this.#o[e];t&&this.#vt(t.texture)}#ai(){this.#Bt();const e=this.#a[this.#L];e&&this.#vt(e,!0),this.#F=0}#j(e){if(this.#A){this.#A.onVisibility(e);return}this.#n.style.visibility=e?"visible":"hidden"}#vt(e,t=!1,i=!0){const s=this.#i;s.bindFramebuffer(s.FRAMEBUFFER,null),s.useProgram(this.#g),s.activeTexture(s.TEXTURE0),s.bindTexture(s.TEXTURE_2D,e),s.uniform1i(this.#E,0),s.uniform1i(this.#b,t?1:0),s.viewport(0,0,this.#M,this.#X),s.drawArrays(s.TRIANGLES,0,3),this.#f={kind:"texture",texture:e,flip:t},this.#j(!0),i&&this.#re++}#li(e,t){let i=0;return this.#we!==0&&!t&&(i=Math.max(0,e-this.#we-1),this.#D.missed+=i),this.#we=e,i}#Mt(e){e-this.#Oe<=K||(this.#Ne=e,this.#W=0,this.#ae=0,this.#le=0,this.#_e=0,this.#ue=0,this.#re=0,this.#Ae=0,this.#de=0,this.#Se=0,this.#me=0)}#Lt(e){const t=e-this.#Ne;if(t<K)return;const i=this.#He()&&(this.#O||this.#q)?this.#le:this.#W,s=this.#W?(this.#ae+this.#_e)/this.#W:0;let r;this.#ce!=null&&(r=0,this.#de!==0&&(r+=this.#Ae/1e6/this.#de),this.#me!==0&&(r+=this.#Se/1e6/this.#me/2));const o={...this.#D,dropped:this.#e.getVideoPlaybackQuality?.().droppedVideoFrames??0,fps:i*1e3/t,frameMs:s,maxQueuedFields:this.#ue,outputFps:this.#re*1e3/t,gpuMs:r,film:this.#q,filmError:this.#ee};this.dispatchEvent(new CustomEvent("stats",{detail:o})),this.#je?.(o),this.#Ne=e,this.#W=0,this.#ae=0,this.#le=0,this.#_e=0,this.#ue=0,this.#re=0,this.#Ae=0,this.#de=0,this.#Se=0,this.#me=0}#Bt(){const e=this.#i;this.#L=(this.#L+1)%y,e.bindTexture(e.TEXTURE_2D,this.#a[this.#L]??null),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,this.#oe),this.#F=Math.min(this.#F+1,y)}#te(e,t,i,s=!0){if(this.#F===0||this.#N)return;s&&(this.#F===y&&!e?this.#D.filtered++:this.#D.degraded++);const r=this.#i,{prev:o,cur:h,next:u}=this.#Ut(e);r.bindFramebuffer(r.FRAMEBUFFER,i),r.useProgram(this.#p);for(const[c,l]of[o,h,u].entries())r.activeTexture(r.TEXTURE0+c),r.bindTexture(r.TEXTURE_2D,this.#a[l]??null);r.uniform1i(this.#u.prev,0),r.uniform1i(this.#u.cur,1),r.uniform1i(this.#u.next,2);const f=this.#k?this.#r?.texture??null:null,a=this.#k?this.#r?.combTexture??null:null,m=f!==null&&a!==null;f!==null&&a!==null&&(r.activeTexture(r.TEXTURE0+3),r.bindTexture(r.TEXTURE_2D,f),r.uniform1i(this.#u.fieldMetrics,3),r.activeTexture(r.TEXTURE0+4),r.bindTexture(r.TEXTURE_2D,a),r.uniform1i(this.#u.comb,4)),r.uniform2i(this.#u.size,this.#M,this.#X);const x=this.#bt?0:1;r.uniform1i(this.#u.parity,t?1-x:x),r.uniform1i(this.#u.tff,this.#bt?1:0),r.uniform1i(this.#u.second,t?1:0),r.uniform1i(this.#u.spatialCheck,this.#se?1:0),r.uniform1i(this.#u.debug,this.#G?1:0),r.uniform1i(this.#u.film,m?1:0),r.uniform1i(this.#u.phase,this.#P.phase),r.viewport(0,0,this.#M,this.#X),r.drawArrays(r.TRIANGLES,0,3),this.#G&&m&&this.#jt(this.#Et,0,90),i===null&&(this.#f={kind:"yadif",flush:e,second:t},this.#j(!0),s&&this.#re++)}#Ut(e){const t=i=>(this.#L+y-i)%y;return this.#F===1?{prev:this.#L,cur:this.#L,next:this.#L}:e?{prev:t(1),cur:this.#L,next:this.#L}:this.#F===2?{prev:t(1),cur:t(1),next:this.#L}:{prev:t(2),cur:t(1),next:this.#L}}#Me(){if(this.#dt(),!this.#I)return;const e=this.#e,t=e.videoWidth,i=e.videoHeight;if(t===0||i===0)return;const s=Math.min(e.offsetWidth/t,e.offsetHeight/i),r=t*s,o=i*s;this.#n.style.left=`${e.offsetLeft+(e.offsetWidth-r)/2}px`,this.#n.style.top=`${e.offsetTop+(e.offsetHeight-o)/2}px`,this.#n.style.width=`${r}px`,this.#n.style.height=`${o}px`}#It(e,t){const i=this.#i;this.#t.width=e,this.#t.height=t,this.#M=e,this.#X=t,this.#F=0,this.#f=null,this.#C(),this.#Me();for(const s of this.#a)i.deleteTexture(s);this.#a=[];for(let s=0;s<y;s++){const r=i.createTexture();i.bindTexture(i.TEXTURE_2D,r),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MAG_FILTER,i.NEAREST),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_S,i.CLAMP_TO_EDGE),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_T,i.CLAMP_TO_EDGE),i.texImage2D(i.TEXTURE_2D,0,i.RGBA,e,t,0,i.RGBA,i.UNSIGNED_BYTE,null),this.#a.push(r)}this.#Le(),(this.#O||this.#k)&&this.#Ot(),this.#r?.resize(e,t),this.#Ee()}#Ot(){const e=this.#i;if(!(this.#o.length===A||this.#M===0)){this.#Le();for(let t=0;t<A;t++){const i=e.createTexture();e.bindTexture(e.TEXTURE_2D,i),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.NEAREST),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.NEAREST),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,this.#M,this.#X,0,e.RGBA,e.UNSIGNED_BYTE,null);const s=e.createFramebuffer();e.bindFramebuffer(e.FRAMEBUFFER,s),e.framebufferTexture2D(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0,e.TEXTURE_2D,i,0);const r=e.checkFramebufferStatus(e.FRAMEBUFFER)===e.FRAMEBUFFER_COMPLETE;if(e.bindFramebuffer(e.FRAMEBUFFER,null),!r){e.deleteFramebuffer(s),e.deleteTexture(i),this.#Le();return}this.#o.push({texture:i,framebuffer:s})}this.#c=A-1}}#Le(){const e=this.#i,t=this.#f?.kind==="texture"?this.#f.texture:null;this.#o.some(i=>i.texture===t)&&(this.#f=null);for(const{texture:i,framebuffer:s}of this.#o)e.deleteFramebuffer(s),e.deleteTexture(i);this.#o=[],this.#C()}#ui(){if(this.#I)return;const e=this.#e.parentElement;if(!e)return;const t=document.createElement("div");t.style.cssText="position:relative;display:inline-block;line-height:0;max-width:100%",e.insertBefore(t,this.#e),t.appendChild(this.#e),t.appendChild(this.#n),this.#I=t,this.#ie?.observe(this.#e),this.#Me()}#ci(){if(this.#A)return;const e=this.#I;this.#I=null,this.#ie?.disconnect(),this.#n.remove(),e?.parentElement&&(e.parentElement.insertBefore(this.#e,e),e.remove())}#Nt=()=>this.#Me();#xt(e){return!this.#m||this.#x==="main"?!1:(this.#m.postMessage({type:"event",name:e,video:this.#ht()}),!0)}#zt=()=>{if(this.#xt("emptied")){this.#K(),this.#j(!1);return}this.#F=0,this.#ge=0,this.#Qe=0,this.#C(),this.#V(),this.#T=0,this.#Gt(),this.#f=null,this.#j(!1)};#Gt(){this.#D={filtered:0,missed:0,degraded:0,discontinuities:0,resynced:0,late:0,queueResetted:0},this.#Ge.fill(0),this.#tt=0,this.#we=0,this.#Ne=0,this.#Oe=0,this.#W=0,this.#ae=0,this.#le=0,this.#_e=0,this.#ue=0,this.#re=0,this.#C(),this.#Ae=0,this.#de=0,this.#Se=0,this.#me=0}#Xt=()=>{if(this.#xt("seeking")){this.#K();return}this.#ye=!1};#Y=e=>{if(e.type==="ratechange"&&(this.#h.captureDriven?this.#Ke():this.#Dt()),(e.type==="pause"||e.type==="ended"||e.type==="seeked"||e.type==="ratechange")&&this.#xt(e.type)){this.#K();return}if(e.type==="seeked"){const i=this.#ye;if(this.#ye=!1,i)return;this.#F=0,this.#C(),this.#V(),this.#f=null,this.#j(!1);return}const t=e.type==="ratechange";if(t&&(this.#T=0,this.#ge=this.#e.currentTime),this.#C(),this.#R&&this.#F>0){const i=this.#kt(),s=i===null?void 0:this.#o[i];i!==null&&s?(this.#c=i,this.#te(!0,!1,s.framebuffer),this.#Pt(i)):this.#te(!0,!1,null)}t&&(this.#F=0,this.#we=0,this.#V())};#$t=e=>{if(e.preventDefault(),this.#A){this.#A.onFailure("the deinterlacer WebGL context was lost");return}this.#x!=="active"&&(this.#N=!0,this.#nt("the deinterlacer WebGL context was lost"),this.stop())}}function ze(n,e,t,i,s,r,o){return new Ne(n,t,{canvas:e,onFailure:i,onVisibility:s,requestAnimationFrame:r,cancelAnimationFrame:o})}function J(n,e){const t=n.createProgram(),i=Z(n,n.VERTEX_SHADER,ke),s=Z(n,n.FRAGMENT_SHADER,e);if(n.attachShader(t,i),n.attachShader(t,s),n.linkProgram(t),n.deleteShader(i),n.deleteShader(s),!n.getProgramParameter(t,n.LINK_STATUS)){const r=n.getProgramInfoLog(t);throw n.deleteProgram(t),new Error(`the deinterlacer failed to link: ${r??"no reason given"}`)}return t}function Z(n,e,t){const i=n.createShader(e);if(!i)throw new Error("the deinterlacer could not create a shader");if(n.shaderSource(i,t),n.compileShader(i),!n.getShaderParameter(i,n.COMPILE_STATUS)){const s=n.getShaderInfoLog(i);throw n.deleteShader(i),new Error(`the deinterlacer failed to compile: ${s??"no reason given"}`)}return i}const S=self;class Ge extends EventTarget{currentTime=0;playbackRate=1;seeking=!1;paused=!0;ended=!1;readyState=0;videoWidth=0;videoHeight=0;parentElement=null;offsetWidth=0;offsetHeight=0;offsetLeft=0;offsetTop=0;#t=[];update(e){this.currentTime=e.currentTime,this.playbackRate=e.playbackRate,this.seeking=e.seeking,this.paused=e.paused,this.ended=e.ended,this.readyState=e.readyState,this.videoWidth=e.videoWidth,this.videoHeight=e.videoHeight,this.#t=e.buffered}get buffered(){return{length:this.#t.length,start:e=>{const t=this.#t[e];if(!t)throw new DOMException("Invalid range index","IndexSizeError");return t.start},end:e=>{const t=this.#t[e];if(!t)throw new DOMException("Invalid range index","IndexSizeError");return t.end}}}getVideoPlaybackQuality(){return{creationTime:performance.now(),droppedVideoFrames:0,totalVideoFrames:0,corruptedVideoFrames:0}}requestVideoFrameCallback(){return 0}cancelVideoFrameCallback(){}}let g=null,b=null,ee=!1;function Xe(n){return S.requestAnimationFrame(n)}function $e(n){S.cancelAnimationFrame(n)}function T(n,e=[]){S.postMessage(n,e)}function Ve(n,e,t){n.doubleRate=e.doubleRate,n.spatialCheck=e.spatialCheck,(n.film!==e.film||t==="film")&&(n.film=e.film),n.debug=e.debug}S.onmessage=n=>{const e=n.data;try{if(e.type==="initialize"){if(typeof S.requestAnimationFrame!="function")throw new Error("requestAnimationFrame is unavailable in this Worker");g=new Ge,g.update(e.video),b=ze(g,e.canvas,e.options,i=>{ee||T({type:"failed",message:i})},i=>T({type:"visibility",visible:i}),Xe,$e);let t=0;b.addEventListener("failure",()=>t++),b.addEventListener("stats",i=>{const{dropped:s,...r}=i.detail;T({type:"stats",stats:r,filmFailure:t})}),b.scan=e.scan,b.videoTimeline=e.videoTimeline,b.enabled=e.enabled,T({type:"ready"});return}if(!g||!b)return;switch(e.type){case"frame":g.update(e.video);try{b.ingestExternalFrame(performance.now(),e.metadata,e.frame)}finally{e.frame.close(),T({type:"consumed",id:e.id})}break;case"settings":Ve(b,e.options,e.retryFilm);break;case"scan":b.scan=e.scan;break;case"timeline":b.videoTimeline=e.videoTimeline;break;case"enabled":b.enabled=e.enabled;break;case"event":g.update(e.video),g.dispatchEvent(new Event(e.name));break;case"capture":g.videoWidth=e.width,g.videoHeight=e.height,b.capture().then(t=>T({type:"capture",id:e.id,image:t},[t])).catch(()=>T({type:"capture",id:e.id,image:null}));break;case"destroy":ee=!0,b.destroy(),b=null,g=null,S.close();break}}catch(t){const i=t instanceof Error?t.message:String(t);T({type:"failed",message:i})}}})();
//# sourceMappingURL=worker-9zbL8zVP.js.map
