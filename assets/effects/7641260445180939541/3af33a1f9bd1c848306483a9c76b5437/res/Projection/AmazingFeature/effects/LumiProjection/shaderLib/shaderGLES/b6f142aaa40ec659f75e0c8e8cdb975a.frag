precision highp float;
precision highp int;

uniform float offsetY_0;
uniform vec2 textExpandRatio;
uniform float shakeX;
uniform float shakeScale;
uniform float shakeY;
uniform mediump sampler2D mainTex;
uniform float scale;
uniform float back_alpha;
uniform float mix_with_black;

varying vec2 v_uv;

void main()
{
    vec2 _t1 = v_uv;
    _t1.y -= (offsetY_0 / textExpandRatio.y);
    _t1.x -= ((shakeX * shakeScale) / textExpandRatio.x);
    _t1.y -= ((shakeY * shakeScale) / textExpandRatio.y);
    mediump vec4 _63 = texture2D(mainTex, _t1);
    vec4 _t2 = _63;
    vec4 _81 = texture2D(mainTex, ((v_uv - vec2(0.5)) * scale) + vec2(0.5)) * back_alpha;
    vec4 _t4 = _81;
    gl_FragData[0] = (mix(_81, vec4(0.0, 0.0, 0.0, _t4.w), vec4(mix_with_black)) * (1.0 - _t2.w)) + _63;
}

