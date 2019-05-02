# Remarker

为不再维护的 [Remarker.be](http://remarker.be) 项目提供非官方支持。

## 使用
在书签栏中添加书签，内容为：

```
javascript:(function()%7Bvar createElement%3Dfunction(tag,attrs)%7Bvar elem%3Ddocument.createElement(tag)%3Bfor(var key in attrs)%7Belem.setAttribute(key,attrs%5Bkey%5D)%3B%7D%3Breturn elem%3B%7D%3Bvar loadJS%3Dfunction(src,success)%7Bvar domScript%3DcreateElement(%27script%27,%7B%27src%27:src,%27type%27:%27text/javascript%27%7D)%3Bsuccess%3Dsuccess%7C%7Cfunction()%7B%7D%3BdomScript.onload%3DdomScript.onreadystatechange%3Dfunction()%7Bif(!this.readyState%7C%7C%27loaded%27%3D%3D%3Dthis.readyState%7C%7C%27complete%27%3D%3D%3Dthis.readyState)%7Bsuccess()%3Bthis.onload%3Dthis.onreadystatechange%3Dnull%3Bthis.parentNode.removeChild(this)%3B%7D%3B%7D%3Bdocument.body.appendChild(domScript)%3B%7D%3BloadJS(%27https://code.jquery.com/jquery-1.8.1.min.js%27,function()%7BloadJS(%27https://remarker.admirable.pro/js/markalbe.js%27)%3B%7D)%3B%7D())%3B
```

在需要使用的网页打开时点击书签即可开始标注。