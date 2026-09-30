(function(){"use strict";const M=`#version 300 es
void main() {
  // From the vertex index alone. There is no geometry here worth a buffer.
  vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
`;function k(n,e,t){const i=n.createProgram(),s=V(n,n.VERTEX_SHADER,t),r=V(n,n.FRAGMENT_SHADER,e);if(n.attachShader(i,s),n.attachShader(i,r),n.linkProgram(i),n.deleteShader(s),n.deleteShader(r),!n.getProgramParameter(i,n.LINK_STATUS)){const h=n.getProgramInfoLog(i);throw n.deleteProgram(i),new Error(`the deinterlacer failed to link: ${h??"no reason given"}`)}return i}function V(n,e,t){const i=n.createShader(e);if(!i)throw new Error("the deinterlacer could not create a shader");if(n.shaderSource(i,t),n.compileShader(i),!n.getShaderParameter(i,n.COMPILE_STATUS)){const s=n.getShaderInfoLog(i);throw n.deleteShader(i),new Error(`the deinterlacer failed to compile: ${s??"no reason given"}`)}return i}const ie=`#version 300 es
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
`,se=`#version 300 es
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
`;function re(n,e){const t=k(n,ie,se),i=n.getAttribLocation(t,"aVertexPosition"),s=n.getAttribLocation(t,"aTextureCoord"),r=n.getUniformLocation(t,"uTexture"),h=n.getUniformLocation(t,"uMatrix"),o=n.getUniformLocation(t,"uUvMatrix"),u=n.getUniformLocation(t,"uTextColor"),f=n.getUniformLocation(t,"uBackColor");if(r==null||h==null||o==null||u==null||f==null)throw new Error("failed to initialize DEBUG_FRAGMENT_SHADER, DEBUG_VERTEX_SHADER");const a=n.createBuffer(),m=n.createBuffer();return{gl:n,...ne(n,e),program:t,programUniforms:{vertex:i,textureCoord:s,texture:r,matrix:h,uvMatrix:o,textColor:u,backColor:f},positionBuffer:a,textureBuffer:m}}function ne(n,e){const t=new OffscreenCanvas(0,0),i=t.getContext("2d"),s=new Map;let r=0;const h=0;let o=1;i.font=e,i.fillStyle="white";for(let f=32;f<128;f++){const a=String.fromCharCode(f),m=i.measureText(a),x=Math.ceil(m.actualBoundingBoxDescent+m.actualBoundingBoxAscent+1),c=Math.ceil(m.actualBoundingBoxLeft+m.actualBoundingBoxRight+1);s.set(a,{x:r,y:h,width:c,height:x,metrics:m}),o=Math.max(o,x),r+=c}t.width=r,t.height=o,i.font=e,i.fillStyle="white";for(const[f,a]of s)i.fillText(f,Math.floor(a.x+a.metrics.actualBoundingBoxLeft+1),Math.floor(a.metrics.actualBoundingBoxAscent+1));const u=n.createTexture();return n.bindTexture(n.TEXTURE_2D,u),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MIN_FILTER,n.LINEAR),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MAG_FILTER,n.LINEAR),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_WRAP_S,n.CLAMP_TO_EDGE),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_WRAP_T,n.CLAMP_TO_EDGE),n.texImage2D(n.TEXTURE_2D,0,n.RGBA,n.RGBA,n.UNSIGNED_BYTE,t),{fontTexture:u,chars:s,textureSize:{width:r,height:o}}}function he(n){const e=n.gl;e.deleteBuffer(n.positionBuffer),e.deleteBuffer(n.textureBuffer),e.deleteTexture(n.fontTexture),e.deleteProgram(n.program)}function oe(n,e,t,i,s,r,h){const o=[],u=[],f=t;for(const x of e){if(x===`
`){t=f,i+=h;continue}const c=n.chars.get(x);if(c==null)continue;if(c.width===1){t+=c.metrics.width;continue}const l=Math.floor(t-c.metrics.actualBoundingBoxLeft),p=Math.floor(i-c.metrics.actualBoundingBoxAscent),v=l+c.width,E=p+c.height;o.push(l,p),u.push(c.x,c.y),o.push(l,E),u.push(c.x,c.y+c.height),o.push(l+c.width,E),u.push(c.x+c.width,c.y+c.height),o.push(v,E),u.push(c.x+c.width,c.y+c.height),o.push(l,p),u.push(c.x,c.y),o.push(v,p),u.push(c.x+c.width,c.y),t+=c.metrics.width}const a=n.gl;a.useProgram(n.program),a.bindBuffer(a.ARRAY_BUFFER,n.positionBuffer),a.bufferData(a.ARRAY_BUFFER,new Float32Array(o),a.STATIC_DRAW),a.vertexAttribPointer(n.programUniforms.vertex,2,a.FLOAT,!1,0,0),a.enableVertexAttribArray(n.programUniforms.vertex),a.bindBuffer(a.ARRAY_BUFFER,n.textureBuffer),a.bufferData(a.ARRAY_BUFFER,new Float32Array(u),a.STATIC_DRAW),a.vertexAttribPointer(n.programUniforms.textureCoord,2,a.FLOAT,!1,0,0),a.enableVertexAttribArray(n.programUniforms.textureCoord),a.activeTexture(a.TEXTURE0),a.bindTexture(a.TEXTURE_2D,n.fontTexture),a.uniform1i(n.programUniforms.texture,0),a.uniform3fv(n.programUniforms.textColor,[1,1,1]),a.uniform3fv(n.programUniforms.backColor,[0,0,0]);function m(x,c,l){const p=[];for(let v=0;v<c;v++)for(let E=0;E<x;E++)p.push(l[E*x+v]);return p}a.uniformMatrix4fv(n.programUniforms.matrix,!1,m(4,4,[1/(s/2),0,0,-1,0,-2/r,0,1,0,0,1,0,0,0,0,1])),a.uniformMatrix3fv(n.programUniforms.uvMatrix,!1,m(3,3,[1/n.textureSize.width,0,0,0,1/n.textureSize.height,0,0,0,1])),a.viewport(0,0,s,r),a.enable(a.BLEND),a.blendFunc(a.SRC_ALPHA,a.ONE_MINUS_SRC_ALPHA),a.drawArrays(a.TRIANGLES,0,o.length/2),a.disable(a.BLEND)}const d={firstRepeatsPrevious:0,secondRepeatsNext:1,secondRepeatsPrevious:2,previousSecondRepeated:3,firstRepeatsNext:4,previousFirstRepeated:5,phase:6},F=7,X=2,U=1,ae=2,I=10,le={a:"uA",b:"uB",fieldMetrics:"uFieldMetrics",first:"uFirst",size:"uSize"},$=16,H=8,ue=`#version 300 es

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
  const int BLOCK_H = ${H};

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
`,ce={second:"uSecond",first:"uFirst",size:"uSize"},P=8,fe=`#version 300 es
precision highp float;

uniform sampler2D uSecond;
uniform sampler2D uFirst;

uniform ivec2 uSize;

layout(location = 0) out vec4 outSecond;
layout(location = 1) out vec4 outFirst;

void main()
{
  ivec2 dst = ivec2(gl_FragCoord.xy);
  ivec2 base = dst * ${P};

  vec4 second = vec4(0.0);
  vec4 first = vec4(0.0);

  for (int y = 0; y < ${P}; ++y) {
    for (int x = 0; x < ${P}; ++x) {
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
`,de={previous:"uPrevious",second:"uSecond",first:"uFirst",size:"uSize"},me=`#version 300 es
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
`,R=16,pe=8,ve={prev:"uPrev",cur:"uCur",first:"uFirst",size:"uSize"},xe=`#version 300 es
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
`,Ee={prev:"uPrev",cur:"uCur",next:"uNext",size:"uSize",parity:"uParity",tff:"uTff",spatialCheck:"uSpatialCheck",debug:"uDebug",film:"uFilm",second:"uSecond",phase:"uPhase",fieldMetrics:"uFieldMetrics",comb:"uComb"},be=`#version 300 es
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
  return phase == ${U} || phase == ${ae};
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
    bool combedBlock = (mixed ? comb[1] : comb[0]) > ${pe}.0;
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
`,_={phase:0,run:0};function L(n,e,t){return Object.fromEntries(Object.entries(t).map(([i,s])=>[i,n.getUniformLocation(e,s)]))}class W{#t;#n;#e;#o;#i;#s;#p;#f;#y;#E=null;#F=null;#a=null;#l=null;#d=0;#h=null;#r=null;#u=0;#k=0;metrics=new Float32Array(F*4);#v=0;#b=0;constructor(e){this.#t=e,this.#n=k(e,ue,M),this.#e=L(e,this.#n,le),this.#o=k(e,fe,M),this.#i=L(e,this.#o,ce),this.#s=k(e,me,M),this.#p=L(e,this.#s,de),this.#f=k(e,xe,M),this.#y=L(e,this.#f,ve)}get texture(){return this.#l?.[this.#d]?.textures[0]??null}get combTexture(){return this.#a?.textures[0]??null}resize(e,t){e===this.#v&&t===this.#b||(this.#v=e,this.#b=t,this.#M())}reset(){const e=this.#t;e.deleteSync(this.#r),this.#r=null,this.#u=0;const t=this.#l?.[this.#d];if(!t)return;const i=new Float32Array(F*4);for(let s=0;s<d.phase;s++)i[s*4+1]=1;e.bindTexture(e.TEXTURE_2D,t.textures[0]??null),e.texSubImage2D(e.TEXTURE_2D,0,0,0,F,1,e.RGBA,e.FLOAT,i)}detect(e,t,i){const s=this.#t;if(this.#v===0||this.#b===0)return;this.#W();const r=this.#E,h=this.#F,o=this.#l;if(r===null||h===null||o===null)return;const u=o[this.#d],f=o[1-this.#d];if(s.bindFramebuffer(s.FRAMEBUFFER,r.framebuffer),s.useProgram(this.#n),this.#c(0,e,this.#e.a),this.#c(1,t,this.#e.b),this.#c(2,u.textures[0],this.#e.fieldMetrics),s.uniform1i(this.#e.first,i),s.uniform2i(this.#e.size,this.#v,this.#b),s.viewport(0,0,r.width,r.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,h.framebuffer),s.useProgram(this.#o),this.#c(0,r.textures[0],this.#i.second),this.#c(1,r.textures[1],this.#i.first),s.uniform2i(this.#i.size,r.width,r.height),s.viewport(0,0,h.width,h.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,f.framebuffer),s.useProgram(this.#s),this.#c(0,u.textures[0],this.#p.previous),this.#c(1,h.textures[0],this.#p.second),this.#c(2,h.textures[1],this.#p.first),s.uniform2i(this.#p.size,h.width,h.height),s.viewport(0,0,F,1),s.drawArrays(s.TRIANGLES,0,3),this.#d=1-this.#d,this.#u++,this.#r!==null){s.bindFramebuffer(s.FRAMEBUFFER,null);return}this.#k=this.#u,s.bindBuffer(s.PIXEL_PACK_BUFFER,this.#h),s.readPixels(0,0,F,1,s.RGBA,s.FLOAT,0),s.bindBuffer(s.PIXEL_PACK_BUFFER,null),s.bindFramebuffer(s.FRAMEBUFFER,null),this.#r=s.fenceSync(s.SYNC_GPU_COMMANDS_COMPLETE,0),s.flush()}measureComb(e,t,i){const s=this.#t;if(this.#v===0||this.#b===0)return;this.#W();const r=this.#a;r!==null&&(s.bindFramebuffer(s.FRAMEBUFFER,r.framebuffer),s.useProgram(this.#f),this.#c(0,e,this.#y.prev),this.#c(1,t,this.#y.cur),s.uniform1i(this.#y.first,i),s.uniform2i(this.#y.size,this.#v,this.#b),s.viewport(0,0,r.width,r.height),s.drawArrays(s.TRIANGLES,0,3),s.bindFramebuffer(s.FRAMEBUFFER,null))}poll(){const e=this.#t,t=this.#r;if(t===null||this.#h===null)return null;switch(e.clientWaitSync(t,0,0)){case e.ALREADY_SIGNALED:case e.CONDITION_SATISFIED:return e.bindBuffer(e.PIXEL_PACK_BUFFER,this.#h),e.getBufferSubData(e.PIXEL_PACK_BUFFER,0,this.metrics),e.bindBuffer(e.PIXEL_PACK_BUFFER,null),e.deleteSync(t),this.#r=null,{phase:this.metrics[d.phase*4]??0,run:this.metrics[d.phase*4+1]??0,age:this.#u-this.#k};default:return null}}destroy(){const e=this.#t;if(this.#M(),this.#l!==null){for(const t of this.#l)D(e,t);this.#l=null}e.deleteSync(this.#r),this.#r=null,e.deleteBuffer(this.#h),this.#h=null,e.deleteProgram(this.#n),e.deleteProgram(this.#o),e.deleteProgram(this.#s),e.deleteProgram(this.#f)}#c(e,t,i){const s=this.#t;s.activeTexture(s.TEXTURE0+e),s.bindTexture(s.TEXTURE_2D,t??null),s.uniform1i(i,e)}#M(){const e=this.#t;this.#E!==null&&D(e,this.#E),this.#F!==null&&D(e,this.#F),this.#a!==null&&D(e,this.#a),this.#E=null,this.#F=null,this.#a=null}#W(){const e=this.#t;if(this.#E===null||this.#F===null||this.#a===null){this.#M();const t=Math.ceil(this.#v/$),i=Math.ceil(this.#b/(H*2));this.#E=C(e,t,i,2),this.#F=C(e,Math.ceil(t/P),Math.ceil(i/P),2),this.#a=C(e,Math.ceil(this.#v/R),Math.ceil(this.#b/R),1)}this.#l===null&&(this.#l=[C(e,F,1,1),C(e,F,1,1)],this.#d=0,this.reset()),this.#h===null&&(this.#h=e.createBuffer(),e.bindBuffer(e.PIXEL_PACK_BUFFER,this.#h),e.bufferData(e.PIXEL_PACK_BUFFER,this.metrics.byteLength,e.STREAM_COPY),e.bindBuffer(e.PIXEL_PACK_BUFFER,null))}}function C(n,e,t,i){const s=n.createFramebuffer();n.bindFramebuffer(n.FRAMEBUFFER,s);const r=[];for(let u=0;u<i;u++){const f=n.createTexture();n.bindTexture(n.TEXTURE_2D,f),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MIN_FILTER,n.NEAREST),n.texParameteri(n.TEXTURE_2D,n.TEXTURE_MAG_FILTER,n.NEAREST),n.texImage2D(n.TEXTURE_2D,0,n.RGBA32F,e,t,0,n.RGBA,n.FLOAT,null),n.framebufferTexture2D(n.FRAMEBUFFER,n.COLOR_ATTACHMENT0+u,n.TEXTURE_2D,f,0),r.push(f)}n.drawBuffers(r.map((u,f)=>n.COLOR_ATTACHMENT0+f));const h=n.checkFramebufferStatus(n.FRAMEBUFFER)===n.FRAMEBUFFER_COMPLETE;n.bindFramebuffer(n.FRAMEBUFFER,null);const o={framebuffer:s,textures:r,width:e,height:t};if(!h)throw D(n,o),new Error("failed to allocate framebuffer");return o}function D(n,{framebuffer:e,textures:t}){n.deleteFramebuffer(e);for(const i of t)n.deleteTexture(i)}function w(n,e=0,t=n.length){const i=new DataView(n.buffer,n.byteOffset,n.byteLength),s=[];for(let r=e;r<t;){if(r+8>t)throw new Error("Incomplete MP4 box");const h=i.getUint32(r);if(h<8||r+h>t)throw new Error("Invalid MP4 box size");s.push({type:String.fromCharCode(...n.subarray(r+4,r+8)),start:r,body:r+8,end:r+h}),r+=h}return s}function ge(n,e){for(const t of w(n,e.body,e.end).filter(i=>i.type==="trak")){let i=t;for(const s of["mdia","minf","stbl","stsd"]){const r=w(n,i.body,i.end).find(h=>h.type===s);if(!r)break;i=r}if(i.type==="stsd")for(const s of w(n,i.body+8,i.end)){if(s.type!=="avc1")continue;const r=w(n,s.body+78,s.end).find(u=>u.type==="avcC");if(!r)throw new Error("AVC sample entry has no avcC");const h=n.slice(r.body,r.end);return{codec:"avc1."+Array.from(h.subarray(1,4)).map(u=>u.toString(16).padStart(2,"0")).join(""),description:h}}}return null}class ye{#t;#n=null;#e=null;#o=[];#i=0;#s=null;#p=[];#f=new Set;#y=!1;#E=!1;#F=!1;#a=!1;#l=!1;#d=new WeakMap;constructor(e){this.#t=e,e.addEventListener("seeking",this.#r),e.addEventListener("ratechange",this.#r)}get active(){return this.#a}append(e){if(this.#F)return;const t=new Uint8Array(e),i=new DataView(e);try{for(const r of w(t)){if(r.type==="moov"){this.#n=ge(t,r);const h=this.#n;h&&VideoDecoder.isConfigSupported(h).then(o=>{this.#d.set(h,o.supported===!0)}).catch(o=>this.#u(o))}if(!(r.type!=="moof"||this.#n===null))for(const h of w(t,r.body,r.end).filter(o=>o.type==="traf")){const o=w(t,h.body,h.end),u=o.find(l=>l.type==="tfhd");if(!u||i.getUint32(u.body+4)!==1)continue;const f=o.find(l=>l.type==="tfdt"),a=o.find(l=>l.type==="trun");if(!f||!a||i.getUint32(f.body)!==16777216||i.getUint32(a.body)!==16781057)throw new Error("Unexpected mpeg2toh264 video fragment layout");let m=Number(i.getBigUint64(f.body+4)),x=r.start+i.getInt32(a.body+8);const c=i.getUint32(a.body+4);if(a.body+12+c*16>a.end)throw new Error("Incomplete video samples");for(let l=0;l<c;l++){const p=a.body+12+l*16,v=i.getUint32(p),E=i.getUint32(p+4),G=i.getUint32(p+8),qe=i.getInt32(p+12);if(x<0||x+E>t.length)throw new Error("Video sample outside fragment");this.#o.push({config:this.#n,decodeTime:m/9e4,timestamp:Math.round((m+qe)*1e6/9e4),duration:Math.round(v*1e6/9e4),type:G&65536?"delta":"key",data:t.subarray(x,x+E)}),m+=v,x+=E}}}const s=this.#t.buffered;if(s.length>0){let r=0;for(let h=0;h<(this.#a?this.#i:this.#o.length);h++){const o=this.#o[h];o.type==="key"&&o.timestamp/1e6<=s.start(0)&&(r=h)}r>0&&(this.#o.splice(0,r),this.#i=Math.max(0,this.#i-r))}}catch(s){this.#u(s)}}take(){if(this.#F||this.#t.playbackRate<=1.25||this.#n===null||this.#d.get(this.#n)!==!0){this.#a&&this.#r();return}this.#a||(this.#r(),this.#a=!0);const e=this.#t.currentTime;try{for(;this.#i<this.#o.length&&(this.#s?.decodeQueueSize??0)<6&&this.#p.length<12;){const i=this.#o[this.#i];if(i.decodeTime>e+.25)break;if(this.#e!==i.config){if(this.#s){if(!this.#E){this.#E=!0;const r=this.#s;r.flush().then(()=>{this.#s===r&&(r.close(),this.#s=null,this.#e=null,this.#E=!1)}).catch(h=>{this.#s===r&&this.#u(h)})}break}const s=new VideoDecoder({output:r=>{this.#s!==s?r.close():this.#h(r)},error:r=>{this.#s===s&&this.#u(r)}});this.#s=s,this.#s.configure(i.config),this.#e=i.config}(i.duration??0)<1e3&&this.#f.add(i.timestamp),this.#s.decode(new EncodedVideoChunk(i)),this.#i++}if(this.#y&&this.#i===this.#o.length&&this.#s&&!this.#E){this.#E=!0;const i=this.#s;i.flush().catch(s=>{this.#s===i&&this.#u(s)})}}catch(i){this.#u(i);return}const t=this.#p[0];return!t||t.timestamp/1e6>e+.003*this.#t.playbackRate?this.#l?null:void 0:(this.#l=!0,this.#p.shift())}#h=e=>{this.#f.delete(e.timestamp)||e.timestamp/1e6<this.#t.currentTime-(this.#l?.1:.04)?e.close():this.#p.push(e)};#r=()=>{this.#s&&this.#s.state!=="closed"&&this.#s.close(),this.#s=null,this.#e=null;for(const e of this.#p)e.close();this.#p=[],this.#f.clear(),this.#E=!1,this.#a=!1,this.#l=!1,this.#i=0;for(let e=0;e<this.#o.length;e++){const t=this.#o[e];t.type==="key"&&t.timestamp/1e6<=this.#t.currentTime&&(this.#i=e)}};finish(){this.#y=!0}suspend(){this.#r()}reset(){this.#r(),this.#o=[],this.#i=0,this.#n=null,this.#y=!1,this.#F=!1}destroy(){this.reset(),this.#t.removeEventListener("seeking",this.#r),this.#t.removeEventListener("ratechange",this.#r)}#u(e){this.#r(),this.#F=!0,console.warn("mpeg2toh264: decoded video input unavailable",e)}}const q=["mozParsedFrames","mozDecodedFrames","mozPresentedFrames","mozPaintedFrames"];function Te(n){return q.every(e=>e in n)}function Fe(n){return n.ownerDocument?.defaultView?.performance.timeOrigin??performance.timeOrigin}const Re=250,_e=500;class we{#t;#n;#e;#o=null;#i=null;#s=null;#p=null;#f=!1;#y=!0;#E=null;#F=null;#a=0;#l;#d;#h=null;#r=null;#u=null;#k=null;#v=0;#b=[];#c=[];constructor(e,t){if(this.#t=e,this.#n=t,this.#e=Te(e)?e:null,this.#l=this.#e===null&&typeof VideoFrame<"u",this.#d=this.#l&&e.playbackRate>1,this.#e){for(const i of["emptied","seeking","seeked"])e.addEventListener(i,this.#I);for(const i of["pause","playing","waiting","ratechange"])e.addEventListener(i,this.#w)}if(this.#l)for(const i of["loadeddata","playing","pause","ended","seeking","seeked","emptied","ratechange"])e.addEventListener(i,this.#W)}get mozDriven(){return this.#e!==null&&!this.#d}get captureDriven(){return this.#d}get hasDelivered(){return this.#f}request(e){if(this.#i===null){if(this.#i=e,this.#d){this.#U();return}this.#o=this.#e?requestAnimationFrame(this.#z):this.#t.requestVideoFrameCallback(this.#Te)}}cancel(){this.#o!==null&&(this.#e?cancelAnimationFrame(this.#o):this.#t.cancelVideoFrameCallback(this.#o)),this.#o=null,this.#i=null,this.#h?.(),this.#h=null,this.#u!==null&&this.#t.cancelVideoFrameCallback(this.#u),this.#u=null,this.#M(),this.#k=null,this.#b=[],this.#I()}destroy(){this.cancel();for(const e of["emptied","seeking","seeked"])this.#t.removeEventListener(e,this.#I);for(const e of["pause","playing","waiting","ratechange"])this.#t.removeEventListener(e,this.#w);for(const e of["loadeddata","playing","pause","ended","seeking","seeked","emptied","ratechange"])this.#t.removeEventListener(e,this.#W)}flush(e){if(this.#d)for(this.#t.ownerDocument!==this.#r&&(this.#h?.(),this.#h=null,this.#U());this.#c.length>0&&this.#i!==null;){const t=this.#c.shift(),i=t.frame;try{this.#P(e,{width:i.visibleRect?.width??i.codedWidth,height:i.visibleRect?.height??i.codedHeight,mediaTime:i.timestamp/1e6,presentedFrames:t.count,expectedDisplayTime:t.at,timeOrigin:performance.timeOrigin,frame:i})}finally{i.close()}}}#M(){for(const e of this.#c)e.frame.close();this.#c=[]}#W=e=>{const t=this.#l&&this.#t.playbackRate>1;if(t!==this.#d){const i=this.#i;this.cancel(),this.#d=t,i!==null&&this.request(i);return}this.#d&&((e.type==="pause"||e.type==="ended")&&this.flush(performance.now()),this.#M(),["seeking","seeked","emptied","ratechange"].includes(e.type)&&(this.#k=null,this.#b=[]),this.#h?.(),this.#h=null,this.#i!==null&&this.#U())};#U(){if(this.#h!==null||this.#i===null||(this.#t.paused||this.#t.ended)&&this.#k!==null)return;this.#u===null&&typeof this.#t.requestVideoFrameCallback=="function"&&(this.#u=this.#t.requestVideoFrameCallback(this.#ie));const e=Math.max(4,8/Math.max(1,this.#t.playbackRate)),t=this.#t.ownerDocument?.defaultView;if(this.#r=this.#t.ownerDocument,t){const i=t.setTimeout(this.#O,e);this.#h=()=>t.clearTimeout(i)}else{const i=setTimeout(this.#O,e);this.#h=()=>clearTimeout(i)}}#ie=()=>{this.#u=null,this.#h?.(),this.#h=null,this.#O()};#O=()=>{this.#h=null;const e=this.#t;if(this.#i===null)return;if(e.readyState<2||e.seeking){this.#U();return}let t,i=!1;try{const s=this.#n?.();if(s===null){this.#U();return}i=s!==void 0,t=s??new VideoFrame(e)}catch(s){if(!(s instanceof DOMException)||s.name!=="InvalidStateError")throw s;this.#U();return}if(t.timestamp===this.#k)t.close();else{let s=1;if(this.#k!==null){const h=t.timestamp-this.#k;if(h>1e3&&h<25e4){this.#b.push(h),this.#b.length>7&&this.#b.shift();const o=[...this.#b].sort((f,a)=>f-a),u=o[Math.floor(o.length/2)];s=Math.max(1,Math.round(h/u))}}this.#k=t.timestamp,this.#v+=s;const r=performance.now()+(i?(t.timestamp/1e6-e.currentTime)*1e3/e.playbackRate:0);for(this.#c.push({frame:t,at:r,count:this.#v});this.#c.length>4;)this.#c.shift().frame.close()}this.#U()};#w=()=>{this.#E=null,this.#F=null,this.#a=0};#I=()=>{this.#s=null,this.#p=null,this.#y=!0,this.#w()};#Te=(e,t)=>{this.#P(e,{width:t.width,height:t.height,mediaTime:t.mediaTime,presentedFrames:t.presentedFrames,expectedDisplayTime:t.expectedDisplayTime,timeOrigin:Fe(this.#t)})};#P=(e,t)=>{const i=this.#i;this.#o=null,this.#i=null,this.#f=!0,i?.(e,t)};#z=e=>{const t=this.#e,i=q.map(o=>t[o]);this.#s?.some((o,u)=>i[u]<o)&&this.#I(),this.#s=i;const s=t.mozPaintedFrames,r=!t.seeking&&t.readyState>=2&&t.videoWidth>0&&t.videoHeight>0,h=this.#p===null&&(s>0||t.paused&&(t.mozPresentedFrames>0||t.mozDecodedFrames>0));if(r&&(h||this.#p!==null&&s!==this.#p)){if(this.#E!==null&&e-this.#E>_e&&(this.#w(),this.#y=!0),!t.paused&&!t.ended){const u=this.#F;if(u&&e-u.at>=Re){const f=s-u.frames;if(f>0){const a=(e-u.at)/f;a>=4&&a<=200&&(this.#a=this.#a?this.#a+(a-this.#a)*.25:a)}this.#F=null}this.#F??={at:e,frames:s}}this.#E=e,this.#p=s;const o=this.#y;this.#y=!1,this.#P(e,{width:t.videoWidth,height:t.videoHeight,mediaTime:t.currentTime,presentedFrames:s,expectedDisplayTime:e,timeOrigin:performance.timeOrigin,mozTiming:{periodMs:this.#a,discontinuity:o}})}else this.#o=requestAnimationFrame(this.#z)}}let Ae=null;const K=.5,y=4,O=5,A=O+1,Q=1e3,N=4,B=200,Se=.25,ke=1e3/60,j=250,Pe=1e3/30,Ce=`#version 300 es
void main() {
  // One triangle over the whole viewport, from the vertex index alone. There
  // is no geometry here worth a buffer: every pixel is the fragment shader's.
  vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
`,De=.75,Me=.1,Y=1,Le=.02,Be=.1,J=1,Ue=4,z=5,Ie=4,Oe={2:0,3:.25,4:.5,5:.75},Ne=`#version 300 es
precision highp float;
uniform sampler2D uField;
uniform bool uFlip;
out vec4 fragColor;
void main() {
  ivec2 position = ivec2(gl_FragCoord.xy);
  if (uFlip) position.y = textureSize(uField, 0).y - 1 - position.y;
  fragColor = texelFetch(uField, position, 0);
}
`,ze={requestAnimationFrame:n=>requestAnimationFrame(n),cancelAnimationFrame:n=>cancelAnimationFrame(n)};class Ge extends EventTarget{encodedVideo;#t;#n;#e;#o;#i;#s=null;#p;#f;#y;#E;#F;#a=[];#l=[];#d=A-1;#h=null;#r=[];#u=null;#k=0;#v=null;#b=null;#c=ke;#M=0;#W=0;#U=0;#ie=0;#O=null;#w(){this.#r.length=0,this.#O=null,this.#ie=0}#I=null;#Te;#P;#z;#se=0;#G;#S;#g=0;#L=0;#V=0;#B=y-1;#R=0;#Fe=0;#je=0;#Be=Number.NaN;#Re=!1;#Ue=0;#re=0;#Ye=0;#yt=0;#_=!1;#Z=0;#Ie=!1;#X=!1;#T=null;#ne=[];#N=!1;#Je;#Ze;#A;#he;#q;#et;#m=null;#x;#_e=!1;#tt=0;#it=!1;#Kt=0;#we=!1;#Oe=!1;#oe=null;#Qt=0;#Ae=new Map;#C={filtered:0,missed:0,degraded:0,discontinuities:0,resynced:0,late:0,queueResetted:0};#ae=0;#Ne=0;#ze=0;#K=0;#le=0;#ue=0;#Se=0;#ce=0;#fe;#Ge=[];#de=[];#ke=0;#me=0;#Pe=0;#pe=0;#Ce=_;#ve=0;#D=_;#Q=!1;#xe=null;#Tt="";#Ve=[0,0,0,0,0,0];#st=0;#ee=null;#rt=null;#nt=0;constructor(e,t={},i=null){super(),this.#e=e,this.#P=t.doubleRate??!1,this.#z=t.spatialCheck??!0,this.#G=t.debug??!1,this.#S=t.film??!1,this.#Je=t.onStats,this.#Ze=t.onFailure,this.#A=i,this.#q=i?"main":t.rendering??"main",this.#et=t.workerUrl??Ae,this.#x=this.#q==="main"?"main":"idle",this.#n=i?i.canvas:document.createElement("canvas"),this.#t=i?.canvas??(this.#q==="main"?this.#n:document.createElement("canvas")),this.#he=e,i||(this.#n.style.cssText="position:absolute;pointer-events:none;visibility:hidden");const s=this.#t.getContext("webgl2",{alpha:!0,antialias:!1,depth:!1,stencil:!1,preserveDrawingBuffer:!1,powerPreference:"high-performance"});if(!(s instanceof WebGL2RenderingContext))throw new Error("this browser has no WebGL2");this.#i=s,this.#S&&(this.#wt(),this.#s=new W(s)),this.#p=Z(s,be);const r=this.#p;this.#f=Object.fromEntries(Object.entries(Ee).map(([h,o])=>[h,s.getUniformLocation(r,o)])),this.#y=Z(s,Ne),this.#E=s.getUniformLocation(this.#y,"uField"),this.#F=s.getUniformLocation(this.#y,"uFlip"),this.#fe=s.getExtension("EXT_disjoint_timer_query_webgl2"),this.#t.addEventListener("webglcontextlost",this.#qt),this.#Te=i?null:new ResizeObserver(()=>this.#Qe()),this.encodedVideo=!i&&typeof VideoDecoder<"u"?new ye(e):null,this.#o=new we(e,()=>this.encodedVideo?.take()),e.addEventListener("emptied",this.#$t),e.addEventListener("resize",this.#Xt),e.addEventListener("pause",this.#J),e.addEventListener("ended",this.#J),e.addEventListener("seeking",this.#Wt),e.addEventListener("seeked",this.#J),e.addEventListener("ratechange",this.#J)}get running(){return this.#_&&(this.#T?.interlaced??!0)}get canvas(){return this.#n}get#Ft(){return this.#T?.topFieldFirst!==!1}#Rt(){return{doubleRate:this.#P,spatialCheck:this.#z,film:this.#S,debug:this.#G}}get enabled(){return this.#Ie}set enabled(e){this.#Ie=e,this.#ht(),this.#m?.postMessage({type:"enabled",enabled:e})}set scan(e){const t=this.#T?.interlaced!==e?.interlaced,i=t||this.#T?.topFieldFirst!==e?.topFieldFirst;this.#T=e,!(i&&(!this.#be()||this.#T!==e))&&(this.#m?.postMessage({type:"scan",scan:e}),i&&(this.#R=0,this.#w(),this.#$(),t&&(this.#g=0),this.#h=null,this.#Y(!1)),this.#ht(),i&&((e?.interlaced??!0)&&(this.#A||this.#x==="main")?this.#Me():this.#dt()))}get scan(){return this.#T}set videoTimeline(e){this.#ne=e,this.#m?.postMessage({type:"timeline",videoTimeline:e}),e.length===0&&(this.#T=null),this.#ht()}get videoTimeline(){return this.#ne}get container(){return this.#I??this.#e}get doubleRate(){return this.#P}set doubleRate(e){e!==this.#P&&(this.#P=e,this.#Ee(),this.#w(),this.#_t())}get spatialCheck(){return this.#z}set spatialCheck(e){e!==this.#z&&(this.#z=e,this.#Ee())}get film(){return this.#S}set film(e){const t=this.#m?this.#rt:this.#ee;if(!(e===this.#S&&(e===!1||t===null))){if(this.#m){this.#S=e,this.#Ee(e?"film":void 0);return}if(e){if(!this.#be())return;try{this.#At()}catch(i){this.#S=!0,this.#Ee(),this.#at(`film detector unavailable: ${i instanceof Error?i.message:String(i)}`);return}}if(this.#S=e,this.#Ee(),!e){if(!this.#be())return;this.#Q=!1,this.#D=_,this.#$(),this.#s?.destroy(),this.#s=null}this.#_t()}}get debug(){return this.#G}set debug(e){e!==this.#G&&(this.#G=e,this.#Ee())}get#jt(){return this.#P||this.#S}#_t(){this.#X||(this.#jt?(this.#L>0&&this.#Vt(),(this.#T?.interlaced??!0)&&(this.#A||this.#x==="main")&&this.#Me()):this.#S||(this.#h=null,this.#Y(!1),this.#Le()))}#Ee(e){this.#m?.postMessage({type:"settings",options:this.#Rt(),retryFilm:e})}#wt(){if(this.#i.getExtension("EXT_color_buffer_float")===null)throw new Error("film needs EXT_color_buffer_float")}#At(){this.#wt(),this.#s??=new W(this.#i),this.#L>0&&this.#s.resize(this.#L,this.#V)}#ht(){this.#Ie&&(this.#ne.length>0||(this.#T?.interlaced??!0))?this.start():this.stop()}#Yt(){return this.#A||this.#q==="main"?!1:this.#x==="starting"||this.#x==="active"?!0:typeof Worker<"u"&&typeof VideoFrame<"u"&&typeof OffscreenCanvas<"u"&&this.#et!==null&&"transferControlToOffscreen"in HTMLCanvasElement.prototype?(this.#St(),!0):this.#q==="auto"?(this.#Xe(),!1):(this.#x="failed",this.#_=!1,!0)}#St(){this.#j(),this.#m?.terminate(),this.#m=null,this.#we=!1,this.#Oe=!1,this.#rt=null,this.#nt=0;let e=this.#n;if(this.#it){e=document.createElement("canvas"),e.className=this.#n.className;const r=this.#n.getAttribute("style");r===null?e.removeAttribute("style"):e.setAttribute("style",r),e.style.visibility="hidden",this.#n.parentElement&&this.#n.replaceWith(e),this.#n=e}const t=++this.#tt;this.#x="starting";let i,s;try{s=e.transferControlToOffscreen(),this.#it=!0,i=new Worker(this.#et,{type:"module"})}catch(r){this.#De(r instanceof Error?r.message:String(r));return}this.#m=i,i.onmessage=r=>{t===this.#tt&&this.#Jt(r.data)},i.onerror=r=>{t===this.#tt&&(r.preventDefault(),this.#De(r.message||"the deinterlacer worker failed"))},i.postMessage({type:"initialize",canvas:s,options:this.#Rt(),scan:this.#T,videoTimeline:this.#ne,enabled:this.#_,video:this.#lt()},[s])}#Jt(e){switch(e.type){case"ready":this.#x="active",this.#_&&(this.#ge(),this.#xt());break;case"failed":this.#De(e.message);break;case"consumed":{this.#we=!1,this.#Oe=!0;const t=this.#oe;this.#oe=null,t&&this.#Pt(t);break}case"visibility":this.#n.style.visibility=e.visible?"visible":"hidden";break;case"stats":{const t={...e.stats,dropped:this.#e.getVideoPlaybackQuality?.().droppedVideoFrames??0},i=t.filmError??null,s=this.#nt;if(this.#rt=i,this.#nt=e.filmFailure,i!==null&&e.filmFailure!==s){this.dispatchEvent(new CustomEvent("failure",{detail:i}));try{this.#Ze?.(i)}catch{}}this.dispatchEvent(new CustomEvent("stats",{detail:t})),this.#Je?.(t);break}case"capture":{const t=this.#Ae.get(e.id);if(this.#Ae.delete(e.id),!t){e.image?.close();break}e.image?t.resolve(e.image):createImageBitmap(this.#e).then(t.resolve,t.reject);break}}}#ot(e){if(this.dispatchEvent(new CustomEvent("failure",{detail:e})),!this.#A)try{this.#Ze?.(e)}catch{}}#at(e){this.#ee!==e&&(this.#ee=e,this.#Q=!1,this.#D=_,this.#$(),this.#s?.destroy(),this.#s=null,this.#ot(e))}#be(){return this.#X?!1:(this.#m||(this.#ee=null),!0)}#De(e){if(this.#x==="starting"&&this.#q==="auto"&&!this.#_e){this.#Xe();return}if(this.#kt(e),!this.#_e){this.#_e=!0,this.#St();return}console.error(`Deinterlacer Worker stopped: ${e}`),this.#x="failed",this.#m?.terminate(),this.#m=null,this.#j(),this.#ot(`deinterlacer worker stopped: ${e}`),this.stop()}#Xe(){const e=this.#t;e.className=this.#n.className;const t=this.#n.getAttribute("style");t===null?e.removeAttribute("style"):e.setAttribute("style",t),e.style.visibility="hidden",this.#n.parentElement&&this.#n.replaceWith(e),this.#n=e,this.#it=!1,this.#m?.terminate(),this.#m=null,this.#x="main",this.#j(),this.#_&&(this.#ge(),this.#xt(),(this.#T?.interlaced??!0)&&this.#Me())}#j(){this.#oe?.frame.close(),this.#oe=null}#kt(e){for(const t of this.#Ae.values())t.reject(new Error(e));this.#Ae.clear()}start(){if(!(this.#_||this.#X||this.#N)&&(this.#Z++,this.#_=!0,this.#Ht(),!!this.#be())){if(this.#Ue=performance.now(),this.#Ye=this.#Ue,this.#Be=Number.NaN,this.#re=this.#e.getVideoPlaybackQuality?.().totalVideoFrames??0,this.#pi(),this.#xt(),this.#Yt()){this.#m?.postMessage({type:"enabled",enabled:!0}),this.#x==="active"&&this.#ge();return}this.#ge(),(this.#T?.interlaced??!0)&&this.#Me()}}stop(){this.#Z++,this.#_&&(this.#_=!1,this.#o.cancel(),this.encodedVideo?.suspend(),this.#li(),this.#dt(),this.#R=0,this.#h=null,this.#Y(!1),this.#j(),this.#m?.postMessage({type:"enabled",enabled:!1}))}destroy(){if(!this.#X){this.#X=!0,this.#Ie=!1,this.stop(),this.#m?.postMessage({type:"destroy"}),this.#m?.terminate(),this.#m=null,this.#j(),this.#kt("the deinterlacer was destroyed"),this.#b?.removeEventListener("visibilitychange",this.#vt),this.#b=null,this.#t.removeEventListener("webglcontextlost",this.#qt),this.#o.destroy(),this.encodedVideo?.destroy(),this.#e.removeEventListener("emptied",this.#$t),this.#e.removeEventListener("resize",this.#Xt),this.#e.removeEventListener("pause",this.#J),this.#e.removeEventListener("ended",this.#J),this.#e.removeEventListener("seeking",this.#Wt),this.#e.removeEventListener("seeked",this.#J),this.#e.removeEventListener("ratechange",this.#J),this.#vi();for(const e of this.#a)this.#i.deleteTexture(e);this.#a=[],this.#Le();for(const e of[...this.#Ge,...this.#de.map(({q:t})=>t)])this.#i.deleteQuery(e);this.#Ge.length=0,this.#de.length=0,this.#s?.destroy(),this.#s=null,this.#xe!==null&&(he(this.#xe),this.#xe=null),this.#i.deleteProgram(this.#p),this.#i.deleteProgram(this.#y),this.#i.getExtension("WEBGL_lose_context")?.loseContext()}}capture(){if(this.#x==="active"&&this.#n.style.visibility==="visible"&&this.#m){const s=++this.#Qt,r=new Promise((h,o)=>{this.#Ae.set(s,{resolve:h,reject:o})});return this.#m.postMessage({type:"capture",id:s,width:this.#e.videoWidth,height:this.#e.videoHeight}),r}if(this.#x==="starting"||this.#x==="failed")return createImageBitmap(this.#e);const e=this.#h;if(this.#A&&(!this.#_||this.#N||!e))return Promise.reject(new Error("no rendered picture is available"));if(!this.#_||this.#N||!e)return createImageBitmap(this.#e);e.kind==="texture"?this.#bt(e.texture,e.flip,!1):this.#te(e.flush,e.second,null,!1);const t=this.#e.videoWidth,i=this.#e.videoHeight;return t>0&&i>0&&(t!==this.#t.width||i!==this.#t.height)?createImageBitmap(this.#t,{resizeWidth:t,resizeHeight:i,resizeQuality:"high"}):createImageBitmap(this.#t)}addEventListener(e,t,i){super.addEventListener(e,t,i)}removeEventListener(e,t,i){super.removeEventListener(e,t,i)}#ge(){this.#A||!this.#_||this.#o.request(this.#ni)}#lt(){const e=[];for(let t=0;t<this.#e.buffered.length;t++)e.push({start:this.#e.buffered.start(t),end:this.#e.buffered.end(t)});return{currentTime:this.#e.currentTime,playbackRate:this.#e.playbackRate,seeking:this.#e.seeking,paused:this.#e.paused,ended:this.#e.ended,readyState:this.#e.readyState,videoWidth:this.#e.videoWidth,videoHeight:this.#e.videoHeight,buffered:e}}#Zt(e,t,i){let s;try{s=i?.clone()??new VideoFrame(this.#e,{timestamp:Math.max(0,Math.round(t.mediaTime*1e6))})}catch(h){const o=h instanceof Error?h.message:String(h);this.#q==="auto"&&!this.#Oe&&!this.#_e?(this.#Xe(),this.#He(e,t)):this.#De(o);return}const r={id:++this.#Kt,frame:s,now:e,metadata:t,video:this.#lt()};if(this.#we){this.#oe?.frame.close(),this.#oe=r;return}this.#Pt(r)}#Pt(e){const t=this.#m;if(!t||this.#x!=="active"){e.frame.close();return}this.#we=!0;const i={type:"frame",id:e.id,frame:e.frame,metadata:e.metadata,video:e.video};try{t.postMessage(i,[e.frame])}catch(s){this.#we=!1,e.frame.close();const r=s instanceof Error?s.message:String(s);this.#q==="auto"&&!this.#Oe&&!this.#_e?(this.#Xe(),this.#He(e.now,e.metadata)):this.#De(r)}}#ei(e,t,i){this.#xe==null&&(this.#xe=re(this.#i,"20px monospace")),oe(this.#xe,e,t,i,this.#L,this.#V,20)}#Ct(e){if(this.#fe==null||this.#de.length>30)return;const t=this.#Ge.pop()??this.#i.createQuery();return this.#i.beginQuery(this.#fe.TIME_ELAPSED_EXT,t),this.#de.push({q:t,isField:e}),t}#$e(e){this.#fe!=null&&(e!=null&&this.#i.endQuery(this.#fe.TIME_ELAPSED_EXT),this.#de=this.#de.filter(({q:t,isField:i})=>{if(this.#i.getQueryParameter(t,this.#i.QUERY_RESULT_AVAILABLE)){const s=this.#i.getQueryParameter(t,this.#i.QUERY_RESULT);return i?(this.#Pe+=s,this.#pe++):(this.#ke+=s,this.#me++),this.#Ge.push(t),!1}return!0}))}#$(){this.#D=_,this.#Ce=_,this.#ve=0,this.#Q=!1,this.#s?.reset()}#ti(){const{prev:e,cur:t,next:i}=this.#zt(!1),s=this.#a[e],r=this.#a[t],h=this.#a[i];if(!s||!r||!h)return;const o=this.#T?.topFieldFirst!==!1?0:1;this.#s?.detect(r,h,o),this.#s?.measureComb(s,r,o)}#ii(){const e=this.#s?.poll()??null;e!==null&&(this.#Ce=e,this.#ve=e.age),this.#ve++;const{phase:t,run:i}=this.#Ce;t===0||this.#ve>Math.ceil(z*Math.max(1,this.#e.playbackRate))?this.#D=_:this.#D={phase:(t-1+this.#ve)%z+1,run:i}}#si(e){const t=[],i=this.#s?.metrics??new Float32Array(0);for(let r=0;r<d.phase;r++){const h=i[r*4]??0,o=i[r*4+1]??0,u=i[r*4+2]??0;t.push(`${h.toFixed(3)},${o.toString().padStart(4)},${u.toFixed(3)}`)}const s=this.#Ve.map((r,h)=>`${h===0?"-":h}:${r}`).join(" ");return`frame=${e} phase=${this.#D.phase} run=${this.#D.run} known=${this.#Ce.phase}/${this.#Ce.run} age=${this.#ve} ${this.#Q?"film":"video"} period=${this.#g.toFixed(3)}
${t.join(" ")}
${s} dropped:${this.#st}`}#ut(e,t){const i=t-performance.timeOrigin;return Number.isFinite(i)&&i!==0?e+i:e}#ri(e,t){const i=e.expectedDisplayTime;if(!Number.isFinite(i)||i<=0||!Number.isFinite(e.timeOrigin))return t;const s=this.#ut(i,e.timeOrigin),r=Ue*Math.max(this.#c,this.#g);return s<t-r||s>t+r?t:s}#ni=(e,t)=>{if(!this.#_||this.#N)return;this.#pt();const i=this.#ut(e,t.timeOrigin);this.#Ue=i,this.#re=Math.max(this.#re,this.#e.getVideoPlaybackQuality?.().totalVideoFrames??0);const{frame:s,...r}=t;this.#he=s??this.#e;try{this.#Dt(i,r,s)}finally{this.#he=this.#e}this.#ge()};#Dt(e,t,i){if(this.#Be=t.mediaTime,this.#x==="active"){this.#Zt(e,t,i);return}this.#x!=="starting"&&this.#He(e,t)}ingestExternalFrame(e,t,i){this.#he=i;try{this.#He(e,t)}finally{this.#he=this.#e}}#He(e,t){const i=this.#Z;if(this.#H(i)&&(this.#hi(t.mediaTime),!!this.#H(i)&&t.width>0&&t.height>0)){let s=!1;if(!this.#Re&&this.#e.seeking){const l=this.#e.buffered,p=this.#g>=N?this.#g/1e3:B/1e3;for(let v=0;v<l.length;v++)if(t.mediaTime>=l.start(v)&&t.mediaTime<l.end(v)&&Math.abs(t.mediaTime-this.#e.currentTime)<=p){s=!0;break}}if(s&&(this.#Re=!0),(this.#L===0||this.#V===0)&&this.#Gt(t.width,t.height),!this.#H(i))return;if(this.#T&&!this.#T.interlaced){const l=performance.now();this.#It(l),this.#Ne=l,this.#di(),this.#le+=performance.now()-l,this.#K++,this.#ue++,this.#Ot(l);return}const r=t.mediaTime-this.#Fe,h=t.mozTiming,o=s||(h?h.discontinuity||r<0||r>K:r<0||r>K);o&&(this.#R=0,this.#g=0,this.#C.discontinuities++,this.#w(),this.#$());const u=this.#mi(t.presentedFrames,o);if(this.#R>0&&t.mediaTime===this.#Fe&&(!h||t.presentedFrames===this.#je))return;if(!o){const l=h?.periodMs??0;l>0?this.#Mt(l*(this.#e.playbackRate||1)/1e3,1):this.#R>0&&r>0&&this.#Mt(r,u+1)}this.#Fe=t.mediaTime,this.#je=t.presentedFrames;const f=performance.now();this.#It(f),this.#Ne=f;const a=performance.now(),m=this.#Ct(!1);if(this.#Nt(),this.#S&&!this.#ee&&!this.#s)try{this.#At()}catch(l){this.#at(`film detector unavailable: ${l instanceof Error?l.message:String(l)}`)}if(!this.#H(i)){this.#X||this.#$e(m);return}if(this.#S&&!this.#ee){if(this.#R===y&&u===0)try{this.#ii(),this.#ti()}catch(l){this.#at(`film detection failed: ${l instanceof Error?l.message:String(l)}`)}else this.#$();this.#Ve[this.#D.phase]=(this.#Ve[this.#D.phase]??0)+1,this.#Q=this.#D.phase!==0&&this.#D.run>=I,this.#G&&(this.#Tt=this.#si(t.presentedFrames))}if(!this.#H(i)){this.#X||this.#$e(m);return}const c=this.#ri(t,e)+this.#c;if(this.#Q)if(this.#We()){const l=this.#D.phase;if(l===U)this.#st++,this.#ie++;else{const p=this.#g*z/Ie,v=this.#ft(1,e,p),E=Oe[l]??0,G=v||this.#O===null?c+p:c+E*this.#g;this.#qe("film",!1,this.#ct("film",G,p),p)}}else this.#te(!1,!1,null);else if(this.#P&&this.#We()){const l=this.#g/2,v=this.#ft(2,e,l)||this.#O===null?c+l*2:c,E=this.#ct("field",v,l);this.#qe("field",!1,E,l),this.#qe("field",!0,E+l,l)}else if(this.#We()){const l=this.#g,v=this.#ft(1,e,l)||this.#O===null?c+l:c;this.#qe("frame",!1,this.#ct("frame",v,l),l)||(this.#C.late++,this.#te(!1,!1,null))}else this.#C.late+=this.#r.length,this.#w(),this.#te(!1,!1,null);this.#ce=Math.max(this.#ce,this.#r.length),this.#$e(m),this.#le+=performance.now()-a,this.#K++,this.#Ot(f)}}#H(e){return!this.#X&&this.#_&&e===this.#Z}#hi(e){const t=this.#Z;let i;for(let h=this.#ne.length-1;h>=0;h--){const o=this.#ne[h];if(o.start<=e+1e-6){i=o;break}}if(i?.codedSize&&(i.codedSize.width!==this.#L||i.codedSize.height!==this.#V)&&this.#Gt(i.codedSize.width,i.codedSize.height),!this.#H(t))return;const s=i?.scan;if(!s||this.#T?.interlaced===s.interlaced&&this.#T.topFieldFirst===s.topFieldFirst)return;const r=this.#T?.interlaced;this.#T=s,this.#R=0,this.#w(),this.#be()&&(r!==s.interlaced&&(this.#g=0),s.interlaced&&(this.#A||this.#x==="main")?this.#Me():this.#dt(),this.#$())}#We(){return(this.#P||this.#S)&&this.#g>0&&this.#l.length===A}#Mt(e,t){const s=e*1e3/(this.#e.playbackRate||1)/t;s<N||s>B||(this.#g=this.#g>0&&s>this.#g*De?this.#g+(s-this.#g)*Se:s)}#qe(e,t,i,s){const r=this.#Lt();if(r===null)return!1;const h=this.#l[r];if(!h)return!1;for(this.#d=r;this.#r.length>0&&this.#r[0]?.slot===r;)this.#r.shift(),this.#C.late++;this.#te(!1,t,h.framebuffer);const o={slot:r,at:i,duration:s,cadence:e,phase:e==="film"?this.#D.phase:e==="field"?t?2:1:0,droppedBefore:this.#ie};return this.#ie=0,this.#r.push(o),this.#O=o,!0}#ct(e,t,i){if(!(i>0))return t;const s=this.#O;if(s!==null&&s.cadence===e){const r=s.at+s.duration,h=t-r;if(Math.abs(h)<i){const o=Math.max(-Y,Math.min(Y,h*Me));return r+o}}s!==null&&this.#C.resynced++;for(let r=this.#r.at(-1);r&&r.at>=t;)this.#r.pop(),this.#C.late++,r=this.#r.at(-1);return t}#ft(e,t,i){const s=this.#r.at(-1),r=(O+1)*Math.max(this.#c,i);if(s&&s.at-t>r)return this.#w(),this.#C.queueResetted++,!0;const h=Math.max(0,this.#r.length+e-O);let o=0,u=0;for(;u<h;){const f=this.#r.shift();if(!f)break;o+=f.duration,u++}for(const f of this.#r)f.at-=o;return this.#C.late+=u,!1}#Lt(){const e=this.#h?.kind==="texture"?this.#h.texture:null,t=new Set(this.#r.map(({slot:s})=>s));for(let s=1;s<=A;s++){const r=(this.#d+s)%A,h=this.#l[r];if(h&&h.texture!==e&&!t.has(r))return r}const i=this.#r[0];if(i){const s=this.#l[i.slot];if(s&&s.texture!==e)return i.slot}return null}#Me(){this.#u===null&&(!this.#_||this.#N||(this.#k=0,this.#u=this.#ye(this.#mt)))}#dt(){this.#Ke(this.#u),this.#u=null,this.#w()}#mt=e=>{if(this.#u=null,!this.#_||this.#N)return;this.#oi(e);const t=this.#Z;this.#o.flush(e),this.#H(t)&&(this.#x==="main"&&this.#ci(this.#M,e),this.#u=this.#ye(this.#mt))};#oi(e){const t=e-this.#k;this.#k=e;const i=Math.max(1,Math.round(t/this.#c)),s=this.#M+i*this.#c,r=e-s;if(this.#M===0||t<=0||t>B||Math.abs(r)>this.#c/4){t>=1&&t<=B&&(this.#c=t),this.#M=e;return}this.#c+=r/i*Le,this.#M=s+r*Be}#Bt(){const e=this.#A;if(e)return{frames:e,origin:performance.timeOrigin};const t=this.#n.ownerDocument?.defaultView??this.#e.ownerDocument?.defaultView??null;return t===null?{frames:ze,origin:performance.timeOrigin}:{frames:t,origin:t.performance.timeOrigin}}#ye(e){const{frames:t,origin:i}=this.#Bt(),s=t.requestAnimationFrame(r=>e(this.#ut(r,i)));return{frames:t,handle:s}}#Ke(e){e?.frames.cancelAnimationFrame(e.handle)}#pt(){if(this.#A)return;this.#ai();const{frames:e}=this.#Bt(),t=this.#u!==null&&this.#u.frames!==e,i=this.#v!==null&&this.#v.frames!==e;!t&&!i||(this.#k=0,t&&(this.#Ke(this.#u),this.#u=this.#ye(this.#mt)),i&&(this.#Ke(this.#v),this.#v=this.#ye(this.#Et)))}#ai(){const e=this.#A?null:this.#n.ownerDocument??null;e!==this.#b&&(this.#b?.removeEventListener("visibilitychange",this.#vt),this.#b=e,e?.addEventListener("visibilitychange",this.#vt))}#vt=()=>{this.#X||this.#pt()};#xt(){this.#A||this.#v!==null||!this.#_||this.#N||(this.#v=this.#ye(this.#Et))}#li(){this.#Ke(this.#v),this.#v=null}#Et=e=>{if(this.#v=null,!this.#_||this.#N)return;const t=this.#Z;this.#o.flush(e),this.#H(t)&&(this.#ui(e),this.#H(t)&&(this.#v=this.#ye(this.#Et)))};#ui(e){if(this.#A||this.#o.captureDriven||this.#o.mozDriven&&this.#o.hasDelivered||e-this.#Ue<j||this.#e.paused||this.#e.ended||this.#e.readyState<2)return;const t=this.#e.currentTime,i=this.#e.getVideoPlaybackQuality?.().totalVideoFrames??0,s=this.#g>=N?this.#g:Pe;(i>0?i>this.#re:t!==this.#Be&&e-this.#Ye>=s*.75)&&(e-this.#yt>=j&&(this.#yt=e,this.#o.cancel(),this.#ge()),this.#re=Math.max(this.#re,i),this.#Ye=e,this.#Dt(e,{mediaTime:t,presentedFrames:Math.max(this.#ae+1,i),expectedDisplayTime:e,timeOrigin:performance.timeOrigin,width:this.#e.videoWidth,height:this.#e.videoHeight}))}#ci(e,t){const i=this.#c/2,s=u=>{const f=u.at-e;return f<=i-J?!0:f>i+J?!1:this.#W>0};for(;this.#r[1]&&s(this.#r[1]);)this.#C.late++,this.#r.shift();const r=this.#r[0];if(!r||!s(r))return;this.#r.shift(),this.#W=r.at-e;const h=performance.now(),o=this.#Ct(!0);this.#Ut(r.slot),this.#$e(o),this.#Se+=performance.now()-h,this.#ue++,this.#G&&this.#fi(r,t),this.#U=t}#fi(e,t){const i=this.#U===0?0:t-this.#U,s=i/this.#c,r=e.cadence==="film"?`phase ${e.phase}`:e.cadence==="field"?`field ${e.phase}`:"frame",h=e.phase===0?"duplicate":`phase ${U}`,o=e.droppedBefore>0?`, ${h} dropped before it`+(e.droppedBefore>1?` (${e.droppedBefore})`:""):"";console.log(`yadif: +${i.toFixed(2)} ms (${s.toFixed(2)} refreshes) ${e.cadence} ${r}, due ${(e.at-t).toFixed(2)} ms${o}`)}#Ut(e){const t=this.#l[e];t&&this.#bt(t.texture)}#di(){this.#Nt();const e=this.#a[this.#B];e&&this.#bt(e,!0),this.#R=0}#Y(e){if(this.#A){this.#A.onVisibility(e);return}this.#n.style.visibility=e?"visible":"hidden"}#bt(e,t=!1,i=!0){const s=this.#i;s.bindFramebuffer(s.FRAMEBUFFER,null),s.useProgram(this.#y),s.activeTexture(s.TEXTURE0),s.bindTexture(s.TEXTURE_2D,e),s.uniform1i(this.#E,0),s.uniform1i(this.#F,t?1:0),s.viewport(0,0,this.#L,this.#V),s.drawArrays(s.TRIANGLES,0,3),this.#h={kind:"texture",texture:e,flip:t},this.#Y(!0),i&&this.#se++}#mi(e,t){let i=0;return this.#ae!==0&&!t&&(i=Math.max(0,e-this.#ae-1),this.#C.missed+=i),this.#ae=e,i}#It(e){e-this.#Ne<=Q||(this.#ze=e,this.#K=0,this.#le=0,this.#ue=0,this.#Se=0,this.#ce=0,this.#se=0,this.#ke=0,this.#me=0,this.#Pe=0,this.#pe=0)}#Ot(e){const t=e-this.#ze;if(t<Q)return;const i=this.#We()&&(this.#P||this.#Q)?this.#ue:this.#K,s=this.#K?(this.#le+this.#Se)/this.#K:0;let r;this.#fe!=null&&(r=0,this.#me!==0&&(r+=this.#ke/1e6/this.#me),this.#pe!==0&&(r+=this.#Pe/1e6/this.#pe/2));const h={...this.#C,dropped:this.#e.getVideoPlaybackQuality?.().droppedVideoFrames??0,fps:i*1e3/t,frameMs:s,maxQueuedFields:this.#ce,outputFps:this.#se*1e3/t,gpuMs:r,film:this.#Q,filmError:this.#ee};this.dispatchEvent(new CustomEvent("stats",{detail:h})),this.#Je?.(h),this.#ze=e,this.#K=0,this.#le=0,this.#ue=0,this.#Se=0,this.#ce=0,this.#se=0,this.#ke=0,this.#me=0,this.#Pe=0,this.#pe=0}#Nt(){const e=this.#i;this.#B=(this.#B+1)%y,e.bindTexture(e.TEXTURE_2D,this.#a[this.#B]??null),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,this.#he),this.#R=Math.min(this.#R+1,y)}#te(e,t,i,s=!0){if(this.#R===0||this.#N)return;s&&(this.#R===y&&!e?this.#C.filtered++:this.#C.degraded++);const r=this.#i,{prev:h,cur:o,next:u}=this.#zt(e);r.bindFramebuffer(r.FRAMEBUFFER,i),r.useProgram(this.#p);for(const[c,l]of[h,o,u].entries())r.activeTexture(r.TEXTURE0+c),r.bindTexture(r.TEXTURE_2D,this.#a[l]??null);r.uniform1i(this.#f.prev,0),r.uniform1i(this.#f.cur,1),r.uniform1i(this.#f.next,2);const f=this.#S?this.#s?.texture??null:null,a=this.#S?this.#s?.combTexture??null:null,m=f!==null&&a!==null;f!==null&&a!==null&&(r.activeTexture(r.TEXTURE0+3),r.bindTexture(r.TEXTURE_2D,f),r.uniform1i(this.#f.fieldMetrics,3),r.activeTexture(r.TEXTURE0+4),r.bindTexture(r.TEXTURE_2D,a),r.uniform1i(this.#f.comb,4)),r.uniform2i(this.#f.size,this.#L,this.#V);const x=this.#Ft?0:1;r.uniform1i(this.#f.parity,t?1-x:x),r.uniform1i(this.#f.tff,this.#Ft?1:0),r.uniform1i(this.#f.second,t?1:0),r.uniform1i(this.#f.spatialCheck,this.#z?1:0),r.uniform1i(this.#f.debug,this.#G?1:0),r.uniform1i(this.#f.film,m?1:0),r.uniform1i(this.#f.phase,this.#D.phase),r.viewport(0,0,this.#L,this.#V),r.drawArrays(r.TRIANGLES,0,3),this.#G&&m&&this.#ei(this.#Tt,0,90),i===null&&(this.#h={kind:"yadif",flush:e,second:t},this.#Y(!0),s&&this.#se++)}#zt(e){const t=i=>(this.#B+y-i)%y;return this.#R===1?{prev:this.#B,cur:this.#B,next:this.#B}:e?{prev:t(1),cur:this.#B,next:this.#B}:this.#R===2?{prev:t(1),cur:t(1),next:this.#B}:{prev:t(2),cur:t(1),next:this.#B}}#Qe(){if(this.#pt(),!this.#I)return;const e=this.#e,t=e.videoWidth,i=e.videoHeight;if(t===0||i===0)return;const s=Math.min(e.offsetWidth/t,e.offsetHeight/i),r=t*s,h=i*s;this.#n.style.left=`${e.offsetLeft+(e.offsetWidth-r)/2}px`,this.#n.style.top=`${e.offsetTop+(e.offsetHeight-h)/2}px`,this.#n.style.width=`${r}px`,this.#n.style.height=`${h}px`}#Gt(e,t){const i=this.#i;this.#t.width=e,this.#t.height=t,this.#L=e,this.#V=t,this.#R=0,this.#h=null,this.#w(),this.#Qe();for(const s of this.#a)i.deleteTexture(s);this.#a=[];for(let s=0;s<y;s++){const r=i.createTexture();i.bindTexture(i.TEXTURE_2D,r),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MAG_FILTER,i.NEAREST),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_S,i.CLAMP_TO_EDGE),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_T,i.CLAMP_TO_EDGE),i.texImage2D(i.TEXTURE_2D,0,i.RGBA,e,t,0,i.RGBA,i.UNSIGNED_BYTE,null),this.#a.push(r)}this.#Le(),(this.#P||this.#S)&&this.#Vt(),this.#s?.resize(e,t),this.#be()}#Vt(){const e=this.#i;if(!(this.#l.length===A||this.#L===0)){this.#Le();for(let t=0;t<A;t++){const i=e.createTexture();e.bindTexture(e.TEXTURE_2D,i),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.NEAREST),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.NEAREST),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,this.#L,this.#V,0,e.RGBA,e.UNSIGNED_BYTE,null);const s=e.createFramebuffer();e.bindFramebuffer(e.FRAMEBUFFER,s),e.framebufferTexture2D(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0,e.TEXTURE_2D,i,0);const r=e.checkFramebufferStatus(e.FRAMEBUFFER)===e.FRAMEBUFFER_COMPLETE;if(e.bindFramebuffer(e.FRAMEBUFFER,null),!r){e.deleteFramebuffer(s),e.deleteTexture(i),this.#Le();return}this.#l.push({texture:i,framebuffer:s})}this.#d=A-1}}#Le(){const e=this.#i,t=this.#h?.kind==="texture"?this.#h.texture:null;this.#l.some(i=>i.texture===t)&&(this.#h=null);for(const{texture:i,framebuffer:s}of this.#l)e.deleteFramebuffer(s),e.deleteTexture(i);this.#l=[],this.#w()}#pi(){if(this.#I)return;const e=this.#e.parentElement;if(!e)return;const t=document.createElement("div");t.style.cssText="position:relative;display:inline-block;line-height:0;max-width:100%",e.insertBefore(t,this.#e),t.appendChild(this.#e),t.appendChild(this.#n),this.#I=t,this.#Te?.observe(this.#e),this.#Qe()}#vi(){if(this.#A)return;const e=this.#I;this.#I=null,this.#Te?.disconnect(),this.#n.remove(),e?.parentElement&&(e.parentElement.insertBefore(this.#e,e),e.remove())}#Xt=()=>this.#Qe();#gt(e){return!this.#m||this.#x==="main"?!1:(this.#m.postMessage({type:"event",name:e,video:this.#lt()}),!0)}#$t=()=>{if(this.#Be=Number.NaN,this.#gt("emptied")){this.#j(),this.#Y(!1);return}this.#R=0,this.#Fe=0,this.#je=0,this.#w(),this.#$(),this.#g=0,this.#Ht(),this.#h=null,this.#Y(!1)};#Ht(){this.#C={filtered:0,missed:0,degraded:0,discontinuities:0,resynced:0,late:0,queueResetted:0},this.#Ve.fill(0),this.#st=0,this.#ae=0,this.#ze=0,this.#Ne=0,this.#K=0,this.#le=0,this.#ue=0,this.#Se=0,this.#ce=0,this.#se=0,this.#w(),this.#ke=0,this.#me=0,this.#Pe=0,this.#pe=0}#Wt=()=>{if(this.#gt("seeking")){this.#j();return}this.#Re=!1};#J=e=>{if((e.type==="pause"||e.type==="ended"||e.type==="seeked"||e.type==="ratechange")&&this.#gt(e.type)){this.#j();return}if(e.type==="seeked"){const i=this.#Re;if(this.#Re=!1,i)return;this.#R=0,this.#w(),this.#$(),this.#h=null,this.#Y(!1);return}const t=e.type==="ratechange";if(t&&(this.#g=0,this.#Fe=this.#e.currentTime),this.#w(),this.#_&&this.#R>0){const i=this.#Lt(),s=i===null?void 0:this.#l[i];i!==null&&s?(this.#d=i,this.#te(!0,!1,s.framebuffer),this.#Ut(i)):this.#te(!0,!1,null)}t&&(this.#R=0,this.#ae=0,this.#$())};#qt=e=>{if(e.preventDefault(),this.#A){this.#A.onFailure("the deinterlacer WebGL context was lost");return}this.#x!=="active"&&(this.#N=!0,this.#ot("the deinterlacer WebGL context was lost"),this.stop())}}function Ve(n,e,t,i,s,r,h){return new Ge(n,t,{canvas:e,onFailure:i,onVisibility:s,requestAnimationFrame:r,cancelAnimationFrame:h})}function Z(n,e){const t=n.createProgram(),i=ee(n,n.VERTEX_SHADER,Ce),s=ee(n,n.FRAGMENT_SHADER,e);if(n.attachShader(t,i),n.attachShader(t,s),n.linkProgram(t),n.deleteShader(i),n.deleteShader(s),!n.getProgramParameter(t,n.LINK_STATUS)){const r=n.getProgramInfoLog(t);throw n.deleteProgram(t),new Error(`the deinterlacer failed to link: ${r??"no reason given"}`)}return t}function ee(n,e,t){const i=n.createShader(e);if(!i)throw new Error("the deinterlacer could not create a shader");if(n.shaderSource(i,t),n.compileShader(i),!n.getShaderParameter(i,n.COMPILE_STATUS)){const s=n.getShaderInfoLog(i);throw n.deleteShader(i),new Error(`the deinterlacer failed to compile: ${s??"no reason given"}`)}return i}const S=self;class Xe extends EventTarget{currentTime=0;playbackRate=1;seeking=!1;paused=!0;ended=!1;readyState=0;videoWidth=0;videoHeight=0;parentElement=null;offsetWidth=0;offsetHeight=0;offsetLeft=0;offsetTop=0;#t=[];update(e){this.currentTime=e.currentTime,this.playbackRate=e.playbackRate,this.seeking=e.seeking,this.paused=e.paused,this.ended=e.ended,this.readyState=e.readyState,this.videoWidth=e.videoWidth,this.videoHeight=e.videoHeight,this.#t=e.buffered}get buffered(){return{length:this.#t.length,start:e=>{const t=this.#t[e];if(!t)throw new DOMException("Invalid range index","IndexSizeError");return t.start},end:e=>{const t=this.#t[e];if(!t)throw new DOMException("Invalid range index","IndexSizeError");return t.end}}}getVideoPlaybackQuality(){return{creationTime:performance.now(),droppedVideoFrames:0,totalVideoFrames:0,corruptedVideoFrames:0}}requestVideoFrameCallback(){return 0}cancelVideoFrameCallback(){}}let g=null,b=null,te=!1;function $e(n){return S.requestAnimationFrame(n)}function He(n){S.cancelAnimationFrame(n)}function T(n,e=[]){S.postMessage(n,e)}function We(n,e,t){n.doubleRate=e.doubleRate,n.spatialCheck=e.spatialCheck,(n.film!==e.film||t==="film")&&(n.film=e.film),n.debug=e.debug}S.onmessage=n=>{const e=n.data;try{if(e.type==="initialize"){if(typeof S.requestAnimationFrame!="function")throw new Error("requestAnimationFrame is unavailable in this Worker");g=new Xe,g.update(e.video),b=Ve(g,e.canvas,e.options,i=>{te||T({type:"failed",message:i})},i=>T({type:"visibility",visible:i}),$e,He);let t=0;b.addEventListener("failure",()=>t++),b.addEventListener("stats",i=>{const{dropped:s,...r}=i.detail;T({type:"stats",stats:r,filmFailure:t})}),b.scan=e.scan,b.videoTimeline=e.videoTimeline,b.enabled=e.enabled,T({type:"ready"});return}if(!g||!b)return;switch(e.type){case"frame":g.update(e.video);try{b.ingestExternalFrame(performance.now(),e.metadata,e.frame)}finally{e.frame.close(),T({type:"consumed",id:e.id})}break;case"settings":We(b,e.options,e.retryFilm);break;case"scan":b.scan=e.scan;break;case"timeline":b.videoTimeline=e.videoTimeline;break;case"enabled":b.enabled=e.enabled;break;case"event":g.update(e.video),g.dispatchEvent(new Event(e.name));break;case"capture":g.videoWidth=e.width,g.videoHeight=e.height,b.capture().then(t=>T({type:"capture",id:e.id,image:t},[t])).catch(()=>T({type:"capture",id:e.id,image:null}));break;case"destroy":te=!0,b.destroy(),b=null,g=null,S.close();break}}catch(t){const i=t instanceof Error?t.message:String(t);T({type:"failed",message:i})}}})();
//# sourceMappingURL=worker-CtAAwC8Z.js.map
