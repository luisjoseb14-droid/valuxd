precision highp float;

varying vec2 uv0;
uniform sampler2D _MainTex;
uniform sampler2D u_Mask;
uniform vec4 u_rtSize;
uniform float u_cutPos;
uniform float u_angle;
uniform float u_lineSize;

void ToLinear(inout vec4 c){
    c.rgb = pow(c.rgb, vec3(2.2));
}
void ToGamma(inout vec4 c){
    c.rgb = pow(c.rgb, vec3(.4545));
}

mat2 rotate2d(float _angle){
    return mat2(cos(_angle),-sin(_angle),
                sin(_angle),cos(_angle));
}

float remap(float smin, float smax, float dmin, float dmax, float value){
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin;
}

void main()
{
    vec2 uv1 = uv0;
    float scale = 7.;

    uv1 -= vec2(0.5);
    uv1.x *= u_rtSize.x / u_rtSize.y;
    uv1 /= scale;
    uv1 += vec2(0.5);

    vec4 res = texture2D(_MainTex, uv0);
    vec4 mask = texture2D(u_Mask, uv1);

    vec2 uv2 = uv0;
    uv2 -= vec2(0.5);
    uv2 = rotate2d(u_angle) * uv2;
    uv2 += vec2(0.5);

    float dis = abs(uv2.x - u_cutPos);
    float line = smoothstep(u_lineSize, 0.0, dis);
    line = pow(line, 2.2);
    res *= line;
    res = res * mask.r + res * (1.-mask.r) * 0.4;

    gl_FragColor = vec4(res);
}
