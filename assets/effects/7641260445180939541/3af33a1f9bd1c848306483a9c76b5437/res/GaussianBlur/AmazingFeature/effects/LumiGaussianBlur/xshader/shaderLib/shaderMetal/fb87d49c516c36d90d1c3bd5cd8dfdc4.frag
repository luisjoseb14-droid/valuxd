#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    float4 u_ScreenParams;
    int u_inverseGammaCorrection;
    float u_gamma;
    float u_sampleX;
    float u_sigmaX;
    float u_spaceDither;
    float u_stepX;
    float u_stepY;
    int u_borderType;
    int u_blurAlpha;
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
float4 _f2(texture2d<float> _p0, sampler _p0Smplr, thread const float2& _p1, constant int& u_inverseGammaCorrection, constant float& u_gamma)
{
    float4 _t3 = _p0.sample(_p0Smplr, _p1);
    if (u_inverseGammaCorrection == 1)
    {
        float4 _105 = _t3;
        float3 _111 = pow(_105.xyz, float3(u_gamma));
        _t3.x = _111.x;
        _t3.y = _111.y;
        _t3.z = _111.z;
    }
    return _t3;
}

static inline __attribute__((always_inline))
float _f1(thread const float& _p0, thread const float& _p1)
{
    return exp((((-0.5) * _p0) * _p0) / (_p1 * _p1));
}

static inline __attribute__((always_inline))
float _f0(thread const float2& _p0, constant float4& u_ScreenParams)
{
    float3 _46 = fract(float3((_p0 * u_ScreenParams.xy).xyx) * 0.103100001811981201171875);
    float3 _t1 = _46 + float3(dot(_46, _46.yzx + float3(33.3300018310546875)));
    return (fract(fract((_t1.x + _t1.y) * _t1.z)) * 2.0) - 1.0;
}

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_inputTexture [[texture(0)]], sampler u_inputTextureSmplr [[sampler(0)]])
{
    main0_out out = {};
    if (buffer.u_sampleX < 9.9999997473787516355514526367188e-06)
    {
        out.o_fragColor = u_inputTexture.sample(u_inputTextureSmplr, in.v_uv);
        return out;
    }
    float2 param = in.v_uv;
    float4 _139 = _f2(u_inputTexture, u_inputTextureSmplr, param, buffer.u_inverseGammaCorrection, buffer.u_gamma);
    float4 _t4 = _139;
    float param_1 = 0.0;
    float param_2 = buffer.u_sigmaX;
    float _146 = _f1(param_1, param_2);
    float _t5 = _146;
    float4 _t6 = _139 * _146;
    float2 _t7 = in.v_uv;
    if (buffer.u_spaceDither > 9.9999997473787516355514526367188e-06)
    {
        float2 param_3 = in.v_uv;
        _t7 += (float2(buffer.u_stepX, buffer.u_stepY) * (buffer.u_spaceDither * _f0(param_3, buffer.u_ScreenParams)));
    }
    float2 _t9 = _t7;
    for (int _t10 = 1; _t10 <= 1024; _t10++)
    {
        float _187 = float(_t10);
        if (_187 > buffer.u_sampleX)
        {
            break;
        }
        float _197 = _187 * buffer.u_stepX;
        float param_4 = _197;
        float param_5 = buffer.u_sigmaX;
        float _203 = _f1(param_4, param_5);
        _t9.x = _t7.x - _197;
        if (_t9.x < 0.0)
        {
            if (buffer.u_borderType == 1)
            {
                _t9.x = 0.0;
                float2 param_6 = _t9;
                _t6 += (_f2(u_inputTexture, u_inputTextureSmplr, param_6, buffer.u_inverseGammaCorrection, buffer.u_gamma) * _203);
                _t5 += _203;
            }
            else
            {
                if (buffer.u_borderType == 2)
                {
                    _t5 += _203;
                }
                else
                {
                    if (buffer.u_borderType == 3)
                    {
                        _t9.x = -_t9.x;
                        float2 param_7 = _t9;
                        _t6 += (_f2(u_inputTexture, u_inputTextureSmplr, param_7, buffer.u_inverseGammaCorrection, buffer.u_gamma) * _203);
                        _t5 += _203;
                    }
                }
            }
        }
        else
        {
            float2 param_8 = _t9;
            _t6 += (_f2(u_inputTexture, u_inputTextureSmplr, param_8, buffer.u_inverseGammaCorrection, buffer.u_gamma) * _203);
            _t5 += _203;
        }
        _t9.x = _t7.x + _197;
        if (_t9.x > 1.0)
        {
            if (buffer.u_borderType == 1)
            {
                _t9.x = 1.0;
                float2 param_9 = _t9;
                _t6 += (_f2(u_inputTexture, u_inputTextureSmplr, param_9, buffer.u_inverseGammaCorrection, buffer.u_gamma) * _203);
                _t5 += _203;
            }
            else
            {
                if (buffer.u_borderType == 2)
                {
                    _t5 += _203;
                }
                else
                {
                    if (buffer.u_borderType == 3)
                    {
                        _t9.x = 2.0 - _t9.x;
                        float2 param_10 = _t9;
                        _t6 += (_f2(u_inputTexture, u_inputTextureSmplr, param_10, buffer.u_inverseGammaCorrection, buffer.u_gamma) * _203);
                        _t5 += _203;
                    }
                }
            }
        }
        else
        {
            float2 param_11 = _t9;
            _t6 += (_f2(u_inputTexture, u_inputTextureSmplr, param_11, buffer.u_inverseGammaCorrection, buffer.u_gamma) * _203);
            _t5 += _203;
        }
    }
    _t6 /= float4(_t5);
    if (buffer.u_inverseGammaCorrection == 1)
    {
        float4 _343 = _t6;
        float3 _348 = pow(_343.xyz, float3(1.0 / buffer.u_gamma));
        _t6.x = _348.x;
        _t6.y = _348.y;
        _t6.z = _348.z;
    }
    if (buffer.u_blurAlpha == 0)
    {
        _t6.w = _t4.w;
    }
    out.o_fragColor = _t6;
    return out;
}

