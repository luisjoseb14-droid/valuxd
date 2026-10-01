#version 300 es
precision highp float;
layout (location = 0) out vec4 FragColor;

uniform sampler2D u_BlurTex;
uniform sampler2D _MainTex;

in vec2 v_local_uv;
in vec2 v_screen_uv;
in vec2 o_uv;
in vec2 m;
in vec2 n;

uniform vec4 u_ScreenParams;

uniform vec2 boxSize;
uniform vec2 boxCenter;
uniform float boxCorner;
uniform float u_alpha;
uniform vec4 u_canvasColor;
float sdRoundBox(in vec2 p, in vec2 b, in vec4 r)
{
    r.xy = (p.x > 0.0) ? r.xy : r.zw;
    r.x = (p.y > 0.0) ? r.x : r.y;
    vec2 q = abs(p) - b + r.x;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r.x;
}

void drawBox(inout vec4 io_output, vec2 _uv, vec2 _size, float _corner, vec2 _adapt)
{
    io_output = vec4(127. / 255., 22. / 255., 253. / 255., 1.);
    vec2 uvd = _uv;
    uvd -= boxCenter;
    uvd -= 0.5;
    uvd *= 1.;
    uvd.y *= _adapt.y / _adapt.x;
    float d = sdRoundBox(uvd, vec2(_size.x, _size.y * (_adapt.y / _adapt.x)), vec4(_corner));
    d = smoothstep(0.01, 0., d);

    io_output *= d;
}

float cut(vec2 x)
{
    return step(0., x.x) * step(x.x, 1.) * step(0., x.y) * step(x.y, 1.);
}

void main()
{
    // //zhe kuai bu yong dong, shi pei yong//
    // vec2 uv = v_local_uv;
    // vec2 x = vec2(0.0);
    // vec2 y = vec2(0.0);
    // x = (m + n) / (2.0 * (v_screen_uv));
    // y = (m - n) / (2.0 * (1. - v_screen_uv));
    // float adapt_width = x.x - y.x;
    // float adapt_height = x.y - y.y;
    // uv.x -= (x.x + y.x) * 0.5;
    // uv.y += (x.y + y.y) * 0.5;
    // uv.x /= (adapt_width * 0.5);
    // uv.y /= (adapt_height * 0.5);
    // uv = uv * 0.5 + 0.5;
    // vec2 adaptSize = vec2(adapt_width, adapt_height);
    // //----------------------------//

    vec2 uv0 = o_uv;

    vec4 mainCol = texture(_MainTex, uv0);
    vec2 maskUV = abs(uv0 - 0.5);
    maskUV = smoothstep(0.5, 0.49, maskUV);
    float mask = maskUV.x * maskUV.y;

    FragColor = (mainCol) * u_alpha;
}
