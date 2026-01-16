#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if(!(cin>>s)) return 0;
    int n=s.size();
    vector<int> z(n,0);

    for(int i=1;i<n;i++) while(i+z[i]<n && s[z[i]]==s[i+z[i]]) z[i]++;

    long long sum=0;
    for(int v:z) sum+=v;
    cout<<sum-1<<"\n";

}
