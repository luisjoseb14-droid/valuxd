precision highp float;

varying vec2 uv0;
uniform sampler2D _MainTex;
uniform vec4 u_rtSize;
uniform float u_cutPos;
uniform float u_angle;
uniform float u_lineSize;

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
    vec4 res = texture2D(_MainTex, uv1);

    uv1 -= vec2(0.5);
    uv1 = rotate2d(u_angle) * uv1;
    uv1 += vec2(0.5);

    float dis = uv1.x - u_cutPos;
    float line = smoothstep(u_lineSize, -0.01, dis);
    line = pow(line, 10.);
    res *= line;

    gl_FragColor = res;
}
