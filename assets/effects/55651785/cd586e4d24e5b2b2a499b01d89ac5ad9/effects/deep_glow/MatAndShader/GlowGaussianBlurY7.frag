precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_InputTex;
uniform float u_Angle;
uniform float u_Strength;
uniform vec4 u_ScreenParams;
uniform float u_DownSample7;
uniform float glow_step;
float normpdf(in float x, in float sigma)
{
	return 0.39894*exp(-0.5*x*x/(sigma*sigma))/sigma;
}



vec4 gaussianBlur(sampler2D i_InputTex, vec2 i_Uv, vec2 i_Dir, float i_Strength)
{
    const int  radius = 32;
    // float s = i_Strength;
    float sigma = 4.0;
    float first = normpdf(0.0, sigma);
    float weight = 0.5 * 1.02 + 0.5;
    weight = first;
    vec4 sum            = vec4(0.0);
    vec4 result         = vec4(0.0);
    vec2 unit_uv        = i_Dir * u_DownSample7 * glow_step;
    vec4 curColor       = texture2D(i_InputTex, i_Uv);
    float gamma = 2.4; 
    vec4 center = pow(curColor, vec4(gamma)) * weight;
    vec4 sum_weight = vec4(weight);

    #ifdef GLOWSAMPLE7
    float s = float(GLOWSAMPLE7);
    for(int i=1;i<=GLOWSAMPLE7;++i)
    {
        float curIndex = float(i);
        vec2 curRightCoordinate = i_Uv+float(i)*unit_uv;
        vec2 curLeftCoordinate  = i_Uv+float(-i)*unit_uv;
        vec4 rightColor = texture2D(i_InputTex, curRightCoordinate);
        vec4 leftColor = texture2D(i_InputTex, curLeftCoordinate);
        rightColor = pow(rightColor, vec4(gamma));
        leftColor = pow(leftColor, vec4(gamma));
        weight = normpdf(curIndex / s * 16.0, sigma);
        sum += (rightColor + leftColor) * weight;
        sum_weight.a += weight * 2.0;
    }
    #endif

    result = (sum + center) / sum_weight.a;
    return pow(result, vec4(1.0 / gamma));
}

void main()
{
    float theta = 90.0 / 180.0 * 3.1415926;
    vec2 ratio = 720.0 * u_ScreenParams.xy / min(u_ScreenParams.x, u_ScreenParams.y);
    ratio = u_ScreenParams.xy;
    vec2 dir = vec2(cos(theta), sin(theta)) / ratio.xy;
    vec4 color = gaussianBlur(u_InputTex, uv0, dir, u_Strength);

    gl_FragColor = color;
}
