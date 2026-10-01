#version 300 es

precision highp float;
layout(location = 0) out vec4 FragColor;

uniform sampler2D _MainTex;
uniform float u_Strength;
uniform vec4 u_ScreenParams;
uniform float u_Steps;

in vec2 v_local_uv;
in vec2 v_screen_uv;
in vec2 m;
in vec2 n;

float normpdf(in float x, in float sigma)
{
	return 0.39894*exp(-0.5*x*x/(sigma*sigma))/sigma;
}
vec4 gaussianBlur(sampler2D i_InputTex, vec2 i_Uv, vec2 i_Dir, float i_Strength)
{
    const int  radius = 32;
    float sigma = 4.0;
    float weight = normpdf(0.0, sigma);

    vec4 sum            = vec4(0.0);
    vec4 result         = vec4(0.0);
    vec2 unit_uv        = i_Dir * u_Steps;
    vec4 gamma         = vec4(1.0);
    vec4 curColor       = texture(i_InputTex, i_Uv);
    vec4 centerPixel    = pow(curColor, vec4(gamma))*weight;
    float sum_weight    = weight;
    float s = i_Strength;
    for(int i=1;i<=1000;i++)
    {
        if (float(i) > s) break;
        vec2 curRightCoordinate = i_Uv+float(i)*unit_uv;
        vec2 curLeftCoordinate  = i_Uv+float(-i)*unit_uv;
        vec4 rightColor = texture(i_InputTex, curRightCoordinate);
        vec4 leftColor = texture(i_InputTex, curLeftCoordinate);
        weight = normpdf(float(i) / s * 13.0, sigma);
        sum+=pow(rightColor, vec4(gamma))*weight;
        sum+=pow(leftColor, vec4(gamma))*weight;
        sum_weight+=weight*2.0;
    }
    result = (sum+centerPixel)/sum_weight;
    // // result.rgb = clamp(sum.rgb+centerPixel.rgb, 0., 1.);
    // // result.a = clamp((sum.a+centerPixel.a)/sum_weight,0.,1.); 
    // // return pow(clamp(result, 0.0, 1.0), vec4(1.0 / gamma));
    return result;
    // result = (sum+centerPixel)/sum_weight; 
    // return pow(clamp(result, 0.0, 1.0), vec4(1.0 / gamma));
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

    float u_Angle = 0.;
    float theta = u_Angle * 3.1415926 / 180.;
    vec2 ratio = 720.0 * u_ScreenParams.xy / min(u_ScreenParams.x, u_ScreenParams.y);
    vec2 dir = vec2(cos(theta), sin(theta)) / ratio;
    vec2 uv0 = uv;
    float extra_val = 1.;
    vec4 color = gaussianBlur(_MainTex, uv0, dir, u_Strength * extra_val);
    color = clamp(color, vec4(0), vec4(1));
    FragColor = color;
}
