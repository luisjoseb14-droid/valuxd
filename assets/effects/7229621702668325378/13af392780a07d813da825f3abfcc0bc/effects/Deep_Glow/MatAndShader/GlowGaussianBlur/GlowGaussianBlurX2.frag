precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_RT1;
uniform float u_Angle;
uniform float u_Strength1;
uniform vec4 u_ScreenParams;
uniform float u_DownSample;

float normpdf(in float x, in float sigma)
{
	return 0.39894*exp(-0.5*x*x/(sigma*sigma))/sigma;
}

vec4 gaussianBlur(sampler2D i_InputTex, vec2 i_Uv, vec2 i_Dir, float i_Strength)
{
    // float s = i_Strength;
    float sigma = 4.0;
    float first = normpdf(0.0, sigma);
    float weight = 0.5 * 1.02 + 0.5;
    weight = first;
    vec4 sum            = vec4(0.0);
    vec4 result         = vec4(0.0);
    vec2 unit_uv        = i_Dir * u_DownSample;
    vec4 curColor       = texture2D(i_InputTex, i_Uv);
    float gamma = 2.4; 
    vec4 center = pow(curColor.aaaa, vec4(gamma)) * weight;
    vec4 sum_weight = vec4(weight);
    #ifdef GLOWSAMPLE2
    float s = float(GLOWSAMPLE2);
    float s1 = s * 0.5;
    float s2 = s1 * 0.5;
    float s3 = s2 * 0.5;
    for(int i=1;i<=GLOWSAMPLE2;++i)
    {
        float curIndex = float(i);
        vec2 curRightCoordinate = i_Uv+float(i)*unit_uv;
        vec2 curLeftCoordinate  = i_Uv+float(-i)*unit_uv;
        vec4 rightColor = texture2D(i_InputTex, curRightCoordinate);
        vec4 leftColor = texture2D(i_InputTex, curLeftCoordinate);
        rightColor = pow(rightColor, vec4(gamma)).aaaa;
        leftColor = pow(leftColor, vec4(gamma)).aaaa;
        if (curIndex <= s3)
        {
            weight = normpdf(curIndex / s3 * 16.0, sigma);
            sum.r += (rightColor.r + leftColor.r) * weight;
            sum_weight.r += weight * 2.0;
        }

        if (curIndex <= s2)
        {
            weight = normpdf(curIndex / s2 * 16.0, sigma);
            sum.g += (rightColor.g + leftColor.g) * weight;
            sum_weight.g += weight * 2.0;
        }

        if (curIndex <= s1)
        {

            weight = normpdf(curIndex / s1 * 16.0, sigma);
            sum.b += (rightColor.b + leftColor.b) * weight;
            sum_weight.b += weight * 2.0;
        }

        weight = normpdf(curIndex / s * 16.0, sigma);
        sum.a += (rightColor.a + leftColor.a) * weight;
        sum_weight.a += weight * 2.0;
    }
    #endif
    result = (sum + center) / sum_weight;
    return pow(result, vec4(1.0 / gamma));
}

void main()
{
    float theta = 0.0;
    vec2 dir = vec2(cos(theta), sin(theta)) / u_ScreenParams.xy;
    vec4 color = gaussianBlur(u_RT1, uv0, dir, u_Strength1);
    gl_FragColor = color;
}
