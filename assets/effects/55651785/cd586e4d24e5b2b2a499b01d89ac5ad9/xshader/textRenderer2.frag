#version 300 es
precision highp float;
in highp vec2 uv0;
in highp vec4 v_ScreenPos;
uniform sampler2D _MainTex;
uniform sampler2D u_NoiseTex;
uniform vec4 u_RectParams2[100];
uniform float u_Index2[100];
uniform int u_Count2;
uniform float u_Alpha[4];
uniform vec2 u_Scale;
uniform float u_Range;
uniform float u_Brightness;
uniform float u_Contrast[4];
uniform vec2 u_TexRect;
out vec4 fragColor;
uniform float u_TypeSettingKind;
float colorAdjust(float c, float brightness, float contrast)
{
    c += brightness;
    c = (c - 0.5) * contrast * 10.0 + 0.5;
    return c;
}

void main()
{

    vec2 uv = uv0;
    vec4 allMask = vec4(0.0);
    vec4 textColor = vec4(0.0);
    vec2 noise = texture(u_NoiseTex,  v_ScreenPos.xy * 0.5 + 0.5).xy;
    float ins = clamp(u_Scale.x, 0.01, 1.0) * u_Range;
    for (int i = 0; i < u_Count2; i++) {
        vec2 t_uv = uv;
        t_uv -= u_RectParams2[i].xy + u_RectParams2[i].zw * 0.5;
        t_uv *= vec2(0.8, 0.8);
        t_uv += u_RectParams2[i].xy + u_RectParams2[i].zw * 0.5;
        float mask = step(u_RectParams2[i].x, t_uv.x) * step(u_RectParams2[i].y, t_uv.y) * step(t_uv.x, u_RectParams2[i].x + u_RectParams2[i].z) * step(t_uv.y, u_RectParams2[i].y + u_RectParams2[i].w);
        vec2 n = noise;
        n.x = colorAdjust(n.x, u_Brightness, u_Contrast[int(u_Index2[i])]);
        n.y = colorAdjust(n.y, u_Brightness, u_Contrast[int(u_Index2[i])]);   
        // allMask = mask * u_Alpha[int(u_Index2[i])];
        vec4 color = texture(_MainTex, uv + ins * (n.xy - 0.5) / u_TexRect.xy * 540.0) * mask * u_Alpha[int(u_Index2[i])];
        textColor = color + textColor * (1.0 - color.a);
    }
    // textColor *= clamp(allMask, 0.0, 1.0);
    fragColor = textColor * 1.0;
}
