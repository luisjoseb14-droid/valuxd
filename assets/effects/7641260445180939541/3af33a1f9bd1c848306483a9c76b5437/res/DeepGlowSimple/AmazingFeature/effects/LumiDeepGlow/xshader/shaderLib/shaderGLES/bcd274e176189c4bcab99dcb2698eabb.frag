precision highp float;
precision highp int;

uniform mediump int u_blendMode;
uniform float u_opacity;
uniform float u_gammaValue;
uniform mediump sampler2D u_inputTex;
uniform mediump sampler2D u_blurTex;
uniform mediump int u_comp;
uniform float u_mult;

varying vec2 v_uv;

vec4 _f8(vec4 _p0)
{
    return vec4(pow(_p0.xyz, vec3(u_gammaValue)), _p0.w);
}

float _f2(float _p0, float _p1)
{
    return 1.0 - ((1.0 - _p0) * (1.0 - _p1));
}

vec3 _f3(vec3 _p0, vec3 _p1)
{
    float param = _p0.x;
    float param_1 = _p1.x;
    float param_2 = _p0.y;
    float param_3 = _p1.y;
    float param_4 = _p0.z;
    float param_5 = _p1.z;
    return vec3(_f2(param, param_1), _f2(param_2, param_3), _f2(param_4, param_5));
}

vec3 _f4(vec3 _p0, vec3 _p1, float _p2)
{
    vec3 param = _p0;
    vec3 param_1 = _p1;
    return (_f3(param, param_1) * _p2) + (_p0 * (1.0 - _p2));
}

vec3 _f0(vec3 _p0, vec3 _p1)
{
    return min(_p0 + _p1, vec3(1.0));
}

vec3 _f1(vec3 _p0, vec3 _p1, float _p2)
{
    vec3 param = _p0;
    vec3 param_1 = _p1;
    return (_f0(param, param_1) * _p2) + (_p0 * (1.0 - _p2));
}

float _f5(float _p0, float _p1)
{
    return _p0 + (_p1 * (1.0 - _p0));
}

vec4 _f6(vec4 _p0, vec4 _p1)
{
    vec3 _t0;
    if (u_blendMode == 0)
    {
        vec3 param = _p0.xyz / vec3(max(_p0.w, 0.001000000047497451305389404296875));
        vec3 param_1 = _p1.xyz / vec3(max(_p0.w, 0.001000000047497451305389404296875));
        float param_2 = u_opacity;
        _t0 = ((_p0.xyz * (1.0 - _p1.w)) + (_p1.xyz * (1.0 - _p0.w))) + (_f4(param, param_1, param_2) * (_p0.w * _p1.w));
    }
    else
    {
        vec3 param_3 = _p0.xyz / vec3(max(_p0.w, 0.001000000047497451305389404296875));
        vec3 param_4 = _p1.xyz / vec3(max(_p0.w, 0.001000000047497451305389404296875));
        float param_5 = u_opacity;
        _t0 = ((_p0.xyz * (1.0 - _p1.w)) + (_p1.xyz * (1.0 - _p0.w))) + (_f1(param_3, param_4, param_5) * (_p0.w * _p1.w));
    }
    float param_6 = _p0.w;
    float param_7 = _p1.w;
    return vec4(_t0, _f5(param_6, param_7));
}

vec4 _f7(vec4 _p0)
{
    return vec4(pow(_p0.xyz, vec3(1.0 / u_gammaValue)), _p0.w);
}

void main()
{
    vec4 param = texture2D(u_inputTex, v_uv);
    vec4 param_1 = texture2D(u_blurTex, v_uv);
    vec4 _289 = _f8(param_1);
    vec4 _t4;
    if (u_comp == 1)
    {
        vec4 param_2 = _f8(param);
        vec4 param_3 = _289;
        _t4 = _f6(param_2, param_3);
    }
    else
    {
        _t4 = _289 * u_opacity;
    }
    vec4 param_4 = _t4 * u_mult;
    vec4 _315 = clamp(_f7(param_4), vec4(0.0), vec4(1.0));
    _t4 = _315;
    gl_FragData[0] = _315;
}

