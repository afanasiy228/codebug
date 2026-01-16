#include <bits/stdc++.h>
using namespace std;

long long modpow(long long a,long long e,long long m) {
    long long r=1%m;
    while(e) {
        if(e&1) r=r*a%m;
        a=a*a%m;
        e>>=1;
    }
    return r;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a,p;
    if(!(cin>>a>>p)) return 0;
    cout<<modpow(a,p-1,p)<<"\n";

}
