#include <bits/stdc++.h>
using namespace std;

long long fact(int n,long long p) {
    long long r=1%p;
    for(int i=2;i<=n;i++) r=r*i%p;
    return r;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long n,k,p;
    if(!(cin>>n>>k>>p)) return 0;
    long long num=fact(n,p);

    long long den=fact(k,p)*fact(n-k,p);

    cout<<(num/den)%p<<"\n";

}
