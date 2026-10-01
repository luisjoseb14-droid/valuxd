#version 300 es

precision highp float;
layout(location = 0) out vec4 FragColor;

// in highp vec2 o_uv;
uniform sampler2D _MainTex;
uniform float u_Intensity;

in vec2 v_local_uv;
in vec2 v_screen_uv;
in vec2 m;
in vec2 n;

float cut(vec2 x){return step(0.,x.x)*step(x.x,1.)*step(0.,x.y)*step(x.y,1.);}

void main()
{
    //zhe kuai bu yong dong, shi pei yong//
    vec2 uv = v_local_uv;
    vec2 x = vec2(0.0);
    vec2 y = vec2(0.0);
    x = (m + n) / (2.0 * (v_screen_uv));
    y = (m - n) / (2.0 * (1. - v_screen_uv));
    float adapt_width = x.x - y.x;
    float adapt_height = x.y - y.y;
    uv.x -= (x.x + y.x) * 0.5;
    uv.y += (x.y + y.y) * 0.5;
    uv.x /= (adapt_width * 0.5);
    uv.y /= (adapt_height * 0.5);
    uv = uv * 0.5 + 0.5;

    vec2 offset = vec2(0.1, 0)*u_Intensity;
    vec2 uv0 = uv;
    vec4 color1 = texture(_MainTex, uv0+offset);
    vec4 color2 = texture(_MainTex, uv0);
    vec4 color3 = texture(_MainTex, uv0-offset);
    vec4 res = vec4(
    color1.r, color2.g, color3.b, 
    max(color1.a, max(color2.a, color3.a)));
    res *= cut(uv);
    FragColor = res;
}
