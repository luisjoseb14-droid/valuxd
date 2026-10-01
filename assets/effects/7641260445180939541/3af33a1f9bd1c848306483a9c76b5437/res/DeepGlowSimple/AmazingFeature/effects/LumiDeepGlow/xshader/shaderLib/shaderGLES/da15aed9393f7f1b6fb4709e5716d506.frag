precision highp float;
precision highp int;

uniform float u_gammaValue;
uniform mediump sampler2D u_inputTex;
uniform float u_stepsInt;
uniform float u_angle;
uniform vec2 u_aspect;
uniform float u_rotate;
uniform float u_steps;
uniform float u_stride;
uniform float u_sigma;

varying vec2 v_uv;

vec2 _f4(vec2 _p0, float _p1)
{
    float _186 = sin(_p1);
    float _189 = cos(_p1);
    return mat2(vec2(_189, -_186), vec2(_186, _189)) * _p0;
}

float _f2(float _p0, float _p1)
{
    return exp((-(_p0 * _p0)) / ((2.0 * _p1) * _p1)) / (2.5066282749176025390625 * _p1);
}

vec3 _f0(vec3 _p0)
{
    return vec3(pow(_p0, vec3(u_gammaValue)));
}

vec3 _f3(float _p0, vec2 _p1, float _p2, float _p3)
{
    float param = 0.0;
    float param_1 = _p3;
    float _t0 = _f2(param, param_1);
    vec3 param_2 = texture2D(u_inputTex, v_uv).xyz;
    float _97 = _t0;
    vec3 _t2 = vec3(0.0);
    int _105 = int(_p0);
    for (mediump int _t4 = 1; _t4 < 32; _t4 += int(u_stepsInt))
    {
        if (_t4 >= _105)
        {
            break;
        }
        mediump float _125 = float(_t4);
        float param_3 = (_125 / _p0) * 15.0;
        float param_4 = _p3;
        float _135 = _f2(param_3, param_4);
        vec2 _141 = (_p1 * _125) * _p2;
        vec3 param_5 = texture2D(u_inputTex, v_uv + _141).xyz;
        vec3 param_6 = texture2D(u_inputTex, v_uv - _141).xyz;
        _t2 += ((_f0(param_5) + _f0(param_6)) * _135);
        _t0 += (_135 * 2.0);
    }
    return (_t2 + (_f0(param_2) * _97)) / vec3(_t0);
}

vec3 _f1(vec3 _p0)
{
    return vec3(pow(_p0, vec3(1.0 / u_gammaValue)));
}

void main()
{
    float _212 = (u_angle / 180.0) * 3.141592502593994140625;
    vec2 param = vec2(cos(_212), sin(_212)) / u_aspect;
    float param_1 = radians(u_rotate);
    float param_2 = u_steps;
    vec2 param_3 = _f4(param, param_1);
    float param_4 = u_stride;
    float param_5 = u_sigma;
    vec3 param_6 = _f3(param_2, param_3, param_4, param_5);
    gl_FragData[0] = vec4(_f1(param_6), 1.0);
}

