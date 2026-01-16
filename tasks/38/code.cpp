#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a,b,c,d,e,f,g,h;
    if(!(cin>>a>>b>>c>>d)) return 0;
    cin>>e>>f>>g>>h;

    long long r1=a*e+b*g;
    long long r2=a*f+b*h;
    long long r3=c*e+d*h;

    long long r4=c*f+d*g;

    cout<<r1<<" "<<r2<<" "<<r3<<" "<<r4<<"\n";

}
