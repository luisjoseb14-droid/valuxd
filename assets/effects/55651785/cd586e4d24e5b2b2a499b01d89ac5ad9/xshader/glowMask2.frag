#version 300 es
precision highp float;
in highp vec2 uv0;
uniform sampler2D _MainTex;
// uniform sampler2D u_Tex2;
uniform vec4 u_RectParams2[200];
uniform float u_Index2[200];
uniform int u_Count2;
uniform float u_Offset[4];
uniform float u_Alpha[4];
uniform float u_TypeSettingKind;
out vec4 fragColor;
void main()
{

    vec2 uv = uv0;
    vec4 textColor = texture(_MainTex, uv);
    float allMask = 0.0;
    float scale = 1.0;
    for (int i = 0; i < u_Count2; i++) {
        vec2 t_uv = uv;
        t_uv -= u_RectParams2[i].xy + u_RectParams2[i].zw * 0.5;
        t_uv *= vec2(0.98, 0.95);
        t_uv += u_RectParams2[i].xy + u_RectParams2[i].zw * 0.5;
        float mask = step(u_RectParams2[i].x, t_uv.x) * step(u_RectParams2[i].y, t_uv.y) * step(t_uv.x, u_RectParams2[i].x + u_RectParams2[i].z) * step(t_uv.y, u_RectParams2[i].y + u_RectParams2[i].w);
        vec2 t_uv_1 = t_uv;
        float slide = t_uv_1.x;
        vec2 slideParams = u_RectParams2[i].xz;
        if (u_TypeSettingKind > 0.5) {
            slide = 1. - t_uv_1.y;
            slideParams = u_RectParams2[i].yw;
        }
        slide -= slideParams.x;
        float ofs = u_Offset[int(u_Index2[i])] * slideParams.y;
        slide -= ofs;
        slide += 0.18;
        float mask1 = smoothstep(0.0, 0.08, slide) * smoothstep(0.18, 0.1, slide) * u_Alpha[int(u_Index2[i])];
        allMask = mask * mask1 + (1.0 - mask) * allMask;
    }
    textColor *= clamp(allMask, 0.0, 1.0);
    fragColor = textColor * 0.0;
}
