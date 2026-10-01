precision highp float;
precision highp int;

uniform mediump sampler2D u_inputTex;
uniform float u_glowFromAlpha;
uniform mediump int u_ca;
uniform float u_redOffset;
uniform float u_greenOffset;
uniform float u_blueOffset;
uniform mediump int u_gamma;
uniform float u_gammaValue;

varying vec2 v_uv;

void main()
{
    mediump vec4 _19 = texture2D(u_inputTex, v_uv);
    vec4 _t0 = _19;
    _t0 = mix(_19, vec4(_t0.w), vec4(u_glowFromAlpha));
    if (u_ca == 1)
    {
        vec4 _t1 = texture2D(u_inputTex, v_uv + vec2(-u_redOffset, u_redOffset)).yzwx;
        float _54 = _t1.w;
        float _57 = _t1.x;
        float _58 = _57 * _54;
        _t1.x = _58;
        _t1 = texture2D(u_inputTex, v_uv + vec2(-u_greenOffset, u_greenOffset)).yzwx;
        float _72 = _t1.w;
        float _75 = _t1.y;
        float _76 = _75 * _72;
        _t1.y = _76;
        _t1 = texture2D(u_inputTex, v_uv + vec2(-u_blueOffset, u_blueOffset)).yzwx;
        float _90 = _t1.w;
        float _93 = _t1.z;
        float _94 = _93 * _90;
        _t1.z = _94;
        _t0 = vec4(_58, _76, _94, 1.0);
    }
    if (u_gamma == 1)
    {
        _t0 = pow(_t0, vec4(u_gammaValue));
    }
    gl_FragData[0] = _t0;
}

