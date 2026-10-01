precision highp float;
precision highp int;

uniform vec2 bulge_radius;
uniform vec2 bulge_center;
uniform float bulge_height;
uniform float cone_radius;
uniform float pinning;
uniform vec4 u_ScreenParams;
uniform mediump sampler2D mainTex;

varying vec2 v_uv;

void _f0(vec2 _p0, vec2 _p1, vec2 _p2, float _p3, float _p4, float _p5, vec2 _p6, inout vec2 _p7)
{
    float _46 = clamp(1.0 - length((((_p0 - vec2(0.5)) + _p2) * 2.0) * (vec2(1.0) / _p1)), 0.0, 1.0);
    vec2 _51 = _p0 - vec2(0.5);
    float _54 = clamp(_p4, 0.0, 1.0);
    float _t4 = 1.0;
    if (_p5 > 0.5)
    {
        vec2 _t5 = vec2((0.00999999977648258209228515625 * _p6.x) / _p6.y, 0.00999999977648258209228515625);
        _t4 = min(min(min(min(_t4, smoothstep(_t5.x, _t5.x * 5.0, v_uv.x)), smoothstep(1.0 - _t5.x, 1.0 - (_t5.x * 5.0), v_uv.x)), smoothstep(_t5.y, _t5.y * 5.0, v_uv.y)), smoothstep(1.0 - _t5.y, 1.0 - (_t5.y * 5.0), v_uv.y));
    }
    _p7 = _51;
    _p7 += ((_51 * (2.0 - length(_51))) * mix(0.0, -_p3, pow(_t4 * (0.001000000047497451305389404296875 + (smoothstep(pow(_54, 2.0) - 0.001000000047497451305389404296875, pow(_54, 0.5) + 0.001000000047497451305389404296875, _46) * _46)), 0.5)));
    _p7 += vec2(0.5);
}

void main()
{
    vec2 param = v_uv;
    vec2 param_1 = bulge_radius;
    vec2 param_2 = bulge_center;
    float param_3 = bulge_height;
    float param_4 = cone_radius;
    float param_5 = pinning;
    vec2 param_6 = u_ScreenParams.xy;
    vec2 param_7;
    _f0(param, param_1, param_2, param_3, param_4, param_5, param_6, param_7);
    gl_FragData[0] = texture2D(mainTex, param_7);
}

