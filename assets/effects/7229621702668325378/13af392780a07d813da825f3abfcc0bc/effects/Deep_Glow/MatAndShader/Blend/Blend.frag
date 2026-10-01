precision highp float;
varying highp vec2 uv0;

uniform sampler2D _MainTex;
uniform sampler2D u_RT1;
uniform sampler2D u_RT0;
uniform sampler2D u_GlowBlurTex;
uniform sampler2D u_GlowBlurTex1;
uniform sampler2D u_Mask;
uniform float u_GlowIntensity;
uniform vec4 u_TextColor;
uniform vec3 u_letterCol;

void main()
{
    float isWhite = step(0.9, u_letterCol.r * u_letterCol.g * u_letterCol.b);
    vec4 dCol = isWhite * vec4(0.549, 0.6706, 1.0, 1.0) + (1. - isWhite) * vec4(1.);
    vec4 tCol = vec4(u_letterCol, 1.) * dCol;

    vec4 oriColor = texture2D(u_RT1, uv0);
    vec4 blurColor = texture2D(u_GlowBlurTex, uv0);
    vec4 blurColor1 = texture2D(u_GlowBlurTex1, uv0);
    float blurGray1 = blurColor.x;
    float blurGray2 = blurColor.y;
    float blurGray3 = blurColor.z;
    float blurGray4 = blurColor.w;
    float blurGray5 = blurColor1.x;
    float blurGray6 = blurColor1.y;
    float blurGray7 = blurColor1.z;
    float blurGray8 = blurColor1.w;
    float intensity = pow(u_GlowIntensity * 0.5, 1./2.4);
    vec4 dis1 = clamp(blurGray1 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis2 = clamp(blurGray2 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis3 = clamp(blurGray3 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis4 = clamp(blurGray4 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis5 = clamp(blurGray5 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis6 = clamp(blurGray6 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis7 = clamp(blurGray7 * intensity * u_TextColor * tCol, 0.0, 1.0);
    vec4 dis8 = clamp(blurGray8 * intensity * u_TextColor * tCol, 0.0, 1.0);
    dis1 = 1. - (1. - dis1) * (1. - dis2);
    dis1 = 1. - (1. - dis1) * (1. - dis3);
    dis1 = 1. - (1. - dis1) * (1. - dis4);
    dis1 = 1. - (1. - dis1) * (1. - dis5);
    dis1 = 1. - (1. - dis1) * (1. - dis6);
    dis1 = 1. - (1. - dis1) * (1. - dis7);
    dis1 = 1. - (1. - dis1) * (1. - dis8);
    vec4 glowColor = clamp(vec4(dis1) * max(intensity, 1.0), 0.0, 1.0);
    glowColor = (1. - (1. - glowColor) * (1. - oriColor));
    glowColor = (1. - (1. - glowColor) * (1. - glowColor));

    vec4 inputCol = texture2D(u_RT0, uv0);
    vec4 mask = texture2D(u_Mask, uv0);

    vec4 res = inputCol + glowColor;
    res = clamp(res, vec4(0.), vec4(1.));
    float alpha = clamp(glowColor.a + inputCol.a, 0., 1.);

    gl_FragColor = vec4(res.rgb, alpha);
}