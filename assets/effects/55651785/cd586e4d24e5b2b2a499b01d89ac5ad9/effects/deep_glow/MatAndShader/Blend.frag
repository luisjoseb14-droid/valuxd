#version 300 es
precision highp float;
layout(location = 0) out vec4 FragColor;

uniform sampler2D u_OriTex;
uniform sampler2D u_GlowBlurTex1;
uniform sampler2D u_GlowBlurTex2;
uniform sampler2D u_GlowBlurTex3;
uniform sampler2D u_GlowBlurTex4;
uniform sampler2D u_GlowBlurTex5;
uniform sampler2D u_GlowBlurTex6;
uniform sampler2D u_GlowBlurTex7;
uniform float u_GlowIntensity;
uniform float u_GlowIntensity1;
uniform float u_GlowIntensity2;
uniform float u_Alpha;

uniform float offset;
uniform float offset2;
uniform float horizontal;

in vec2 v_local_uv;
in vec2 v_screen_uv;
in vec2 m;
in vec2 n;

uniform vec4 u_ScreenParams;
const vec3 GLOW_COL = vec3(37./255., 155./255., 255./255.);

float cut(vec2 x){return step(0.,x.x)*step(x.x,1.)*step(0.,x.y)*step(x.y,1.);}

vec4 getGlowCol(
    vec4 _col1, vec4 _col2,
    vec4 _col3, vec4 _col4,
    vec4 _col5, vec4 _col6,
    vec4 _col7, float ins){

    float intensity = pow(ins * 0.5, 1./2.4);
    vec4 dis1 = clamp(_col1 * intensity, 0.0, 1.0);
    vec4 dis2 = clamp(_col2 * intensity, 0.0, 1.0);
    vec4 dis3 = clamp(_col3 * intensity, 0.0, 1.0);
    vec4 dis4 = clamp(_col4 * intensity, 0.0, 1.0);
    vec4 dis5 = clamp(_col5 * intensity, 0.0, 1.0);
    vec4 dis6 = clamp(_col6 * intensity, 0.0, 1.0);
    vec4 dis7 = clamp(_col7 * intensity, 0.0, 1.0);
    dis1 = 1. - (1. - dis1) * (1. - dis2);
    dis1 = 1. - (1. - dis1) * (1. - dis3);
    dis1 = 1. - (1. - dis1) * (1. - dis4);
    dis1 = 1. - (1. - dis1) * (1. - dis5);
    dis1 = 1. - (1. - dis1) * (1. - dis6);
    dis1 = 1. - (1. - dis1) * (1. - dis7);
    vec4 glowColor = clamp(vec4(dis1) * max(intensity, 1.0), 0.0, 1.0);
    return glowColor;
}

vec4 glow1(vec2 uv, vec2 _l_uv, float ins, float _adaptRatio)
{
    vec4 oriColor = texture(u_OriTex, uv);
    vec4 blurColor1 = texture(u_GlowBlurTex1, uv);
    vec4 blurColor2 = texture(u_GlowBlurTex2, uv);
    vec4 blurColor3 = texture(u_GlowBlurTex3, uv);
    vec4 blurColor4 = texture(u_GlowBlurTex4, uv);
    vec4 blurColor5 = texture(u_GlowBlurTex5, uv);
    vec4 blurColor6 = texture(u_GlowBlurTex6, uv);
    vec4 blurColor7 = texture(u_GlowBlurTex7, uv);



    vec4 glowColor1 = getGlowCol(
        blurColor1,
        blurColor2,
        blurColor3,
        blurColor4,
        blurColor5,
        blurColor6,
        blurColor7,
        u_GlowIntensity1
    );
    vec4 glowColor2 = getGlowCol(
        blurColor1,
        blurColor2,
        blurColor3,
        blurColor4,
        blurColor5,
        blurColor6,
        blurColor7,
        u_GlowIntensity2
    );

    glowColor2.rgb *= GLOW_COL;
    vec2 maskUv1 = _l_uv;
    vec2 maskUv2 = _l_uv;
    if(horizontal < 0.5){
        maskUv1.y = (1.-maskUv1.y) - offset;
        maskUv1.x -= 0.5;
        maskUv1.y /= _adaptRatio;
        maskUv2.y = (1.-maskUv2.y) - offset2;
        maskUv2.x -= 0.5;
        maskUv2.y /= _adaptRatio;
    }else{
        maskUv1.x -= offset;
        maskUv1.y -= 0.5;
        maskUv1.x *= _adaptRatio;
        maskUv2.x -= offset2;
        maskUv2.y -= 0.5;
        maskUv2.x *= _adaptRatio;
    }
    float mask1 = length(maskUv1*0.7);
    mask1 = pow(mask1, 1.5);
    mask1 = smoothstep(1., 0., mask1);
    float mask2 = length(maskUv2*0.4);
    // mask2 = pow(mask2, 0.5);
    mask2 = smoothstep(1., 0., mask2);
    mask2 = max(mask2, smoothstep(0.2, -0.2, _l_uv.x-offset2));
    mask2 = clamp(mask2, 0., 1.);

    // glowColor1 *= mask2;

    vec4 oriColor1 = (1. - (1. - glowColor1) * (1. - oriColor));
    vec4 oriColor2 = (1. - (1. - glowColor2) * (1. - oriColor));

    // oriColor = oriColor1 * mask2 + oriColor2 * mask1;
    // oriColor = vec4(mask1, mask2, 0, 1);

    glowColor1 = glowColor1 * (1.-mask1) + glowColor2 * mask1;
    // glowColor1 += glowColor2 * mask1;
    oriColor = (1. - (1. - glowColor1) * (1. - oriColor));
    return oriColor;
}


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
    //----------------------------//

    vec2 uv0 = v_screen_uv;

    vec4 oriColor = glow1(uv0, uv, u_GlowIntensity, adapt_width/adapt_height) * u_Alpha;
    FragColor = oriColor;
}
