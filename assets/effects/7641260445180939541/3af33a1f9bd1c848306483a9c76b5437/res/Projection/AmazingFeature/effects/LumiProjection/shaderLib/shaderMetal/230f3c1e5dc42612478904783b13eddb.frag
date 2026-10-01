#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    float2 bulge_radius;
    float2 bulge_center;
    float bulge_height;
    float cone_radius;
    float pinning;
    float4 u_ScreenParams;
};

struct main0_out
{
    float4 o_fragColor [[color(0)]];
};

struct main0_in
{
    float2 v_uv [[user(locn0)]];
};

static inline __attribute__((always_inline))
void _f0(thread const float2& _p0, thread const float2& _p1, thread const float2& _p2, thread const float& _p3, thread const float& _p4, thread const float& _p5, thread const float2& _p6, thread float2& _p7, thread float2& v_uv)
{
    float _46 = fast::clamp(1.0 - length((((_p0 - float2(0.5)) + _p2) * 2.0) * (float2(1.0) / _p1)), 0.0, 1.0);
    float2 _51 = _p0 - float2(0.5);
    float _54 = fast::clamp(_p4, 0.0, 1.0);
    float _t4 = 1.0;
    if (_p5 > 0.5)
    {
        float2 _t5 = float2((0.00999999977648258209228515625 * _p6.x) / _p6.y, 0.00999999977648258209228515625);
        _t4 = fast::min(fast::min(fast::min(fast::min(_t4, smoothstep(_t5.x, _t5.x * 5.0, v_uv.x)), smoothstep(1.0 - _t5.x, 1.0 - (_t5.x * 5.0), v_uv.x)), smoothstep(_t5.y, _t5.y * 5.0, v_uv.y)), smoothstep(1.0 - _t5.y, 1.0 - (_t5.y * 5.0), v_uv.y));
    }
    _p7 = _51;
    _p7 += ((_51 * (2.0 - length(_51))) * mix(0.0, -_p3, pow(_t4 * (0.001000000047497451305389404296875 + (smoothstep(pow(_54, 2.0) - 0.001000000047497451305389404296875, pow(_54, 0.5) + 0.001000000047497451305389404296875, _46) * _46)), 0.5)));
    _p7 += float2(0.5);
}

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> mainTex [[texture(0)]], sampler mainTexSmplr [[sampler(0)]])
{
    main0_out out = {};
    float2 param = in.v_uv;
    float2 param_1 = buffer.bulge_radius;
    float2 param_2 = buffer.bulge_center;
    float param_3 = buffer.bulge_height;
    float param_4 = buffer.cone_radius;
    float param_5 = buffer.pinning;
    float2 param_6 = buffer.u_ScreenParams.xy;
    float2 param_7;
    _f0(param, param_1, param_2, param_3, param_4, param_5, param_6, param_7, in.v_uv);
    out.o_fragColor = mainTex.sample(mainTexSmplr, param_7);
    return out;
}

