#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;

    if(n<2) {
        cout<<0<<"\n";
        return 0;
    }

    vector<bool> prime(n,true);

    prime[0]=prime[1]=false;

    for(int p=2;p*p<n;p++) if(prime[p]) for(int j=p*p;j<n;j+=p) prime[j]=false;

    int cnt=0;
    for(bool v:prime) if(v) cnt++;
    cout<<cnt<<"\n";

}
