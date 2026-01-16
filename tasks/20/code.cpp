#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a,b,m;
    if(!(cin>>a>>b>>m)) return 0;

    long long res=1%m;

    while(b>0) {

        if(b&1) res = (res * a) % m;

        a = a * a;

        b >>= 1;

    }

    cout<<res% m<<"\n";

}
